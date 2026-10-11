
import math
import re

from collections import defaultdict

from django.core.cache import cache
from django.db.models import F
from django.utils import timezone
from django.utils.html import strip_tags

from .models import Post, PostInteraction


CACHE_TTL = 60

ACTION_WEIGHTS = {
    "view": 1.0,
    "like": 3.0,
    "save": 4.0,
    "share": 5.0,
    "dismiss": -4.0,
}


def cache_key(user_id):
    return f"personalized_feed:v1:user:{user_id}"


def tokenize(text):
    return set(
        re.findall(
            r"[a-z0-9+#.-]{2,}",
            (text or "").lower(),
        )
    )


def post_text(post):
    content = strip_tags(post.content_html or "")
    keywords = " ".join(
        word for word in (post.keywords or [])
        if isinstance(word, str)
    )

    return f"{post.title or ''} {keywords} {content}"


def normalize(scores):
    positive = {
        key: max(0.0, value)
        for key, value in scores.items()
    }
    maximum = max(positive.values(), default=0.0)

    if not maximum:
        return {}

    return {
        key: value / maximum
        for key, value in positive.items()
    }


def build_profile(user):
    categories = defaultdict(float)
    keywords = defaultdict(float)
    words = defaultdict(float)

    # Creating a post is an explicit interest signal.
    created_posts = Post.objects.filter(
        created_by=user,
        is_published=True,
        is_draft=False,
    ).only(
        "category_id",
        "keywords",
        "title",
        "content_html",
    )

    for post in created_posts:
        if post.category_id:
            categories[post.category_id] += 2.0

        for keyword in post.keywords or []:
            if isinstance(keyword, str):
                keywords[keyword.lower()] += 2.0

        for word in tokenize(post_text(post)):
            words[word] += 1.0

    # Reading and engagement history.
    interactions = (
        PostInteraction.objects
        .filter(user=user)
        .select_related("post")
        .only(
            "action",
            "created_at",
            "post__category_id",
            "post__keywords",
            "post__title",
            "post__content_html",
        )
    )

    now = timezone.now()

    for event in interactions.iterator():
        age_days = max(
            0.0,
            (now - event.created_at).total_seconds() / 86400,
        )
        decay = math.exp(
            -math.log(2) * age_days / 30
        )

        weight = ACTION_WEIGHTS[event.action] * decay
        post = event.post

        if post.category_id:
            categories[post.category_id] += weight

        for keyword in post.keywords or []:
            if isinstance(keyword, str):
                keywords[keyword.lower()] += weight

        # A dismissal is negative feedback, not a positive
        # signal for the dismissed post's content.
        if event.action != PostInteraction.Action.DISMISS:
            for word in tokenize(post_text(post)):
                words[word] += weight

    return (
        normalize(categories),
        normalize(keywords),
        normalize(words),
    )


def compute_ranked_ids(user, limit=1000):
    category_scores, keyword_scores, word_scores = (
        build_profile(user)
    )

    candidates = list(
        Post.objects.filter(
            is_published=True,
            is_draft=False,
        )
        .exclude(created_by=user)
        .select_related("category")
        .order_by("-created_at")[:10000]
    )

    dismissed_ids = set(
        PostInteraction.objects.filter(
            user=user,
            action=PostInteraction.Action.DISMISS,
        ).values_list("post_id", flat=True)
    )

    viewed_ids = set(
        PostInteraction.objects.filter(
            user=user,
            action=PostInteraction.Action.VIEW,
        ).values_list("post_id", flat=True)
    )

    now = timezone.now()
    ranked = []

    for post in candidates:
        if post.id in dismissed_ids:
            continue

        category_score = category_scores.get(
            post.category_id, 0.0
        )

        post_keywords = {
            k.lower()
            for k in (post.keywords or [])
            if isinstance(k, str)
        }

        keyword_score = max(
            (
                keyword_scores.get(k, 0.0)
                for k in post_keywords
            ),
            default=0.0,
        )

        post_words = tokenize(post_text(post))
        text_score = (
            sum(word_scores.get(w, 0.0) for w in post_words)
            / max(1, len(post_words))
        )
        text_score = min(1.0, text_score)

        age_days = max(
            0.0,
            (now - post.created_at).total_seconds() / 86400,
        )
        freshness = math.exp(-age_days / 14)

        score = (
            0.50 * category_score
            + 0.25 * keyword_score
            + 0.15 * text_score
            + 0.10 * freshness
        )

        # Trending is a small tie-breaker, not the main signal.
        if post.is_trending:
            score += 0.03

        # Small discovery bonus for unseen posts.
        if post.id not in viewed_ids:
            score += 0.03

        ranked.append((score, post.created_at, post.id))

    ranked.sort(reverse=True)
    return [post_id for _, _, post_id in ranked[:limit]]


def get_recommended_posts(user, limit=20):
    key = cache_key(user.id)

    ranked_ids = cache.get(key)

    if ranked_ids is None:
        ranked_ids = compute_ranked_ids(user)
        cache.set(key, ranked_ids, CACHE_TTL)

    selected_ids = ranked_ids[:limit]

    if not selected_ids:
        return []

    # Preserve the recommendation order in the database query.
    from django.db.models import Case, When, IntegerField

    ordering = Case(
        *[
            When(pk=post_id, then=position)
            for position, post_id in enumerate(selected_ids)
        ],
        output_field=IntegerField(),
    )

    posts = Post.objects.filter(
        pk__in=selected_ids,
        is_published=True,
        is_draft=False,
    ).select_related("category", "created_by").order_by(ordering)

    return list(posts)


def invalidate_feed_cache(user_id):
    cache.delete(cache_key(user_id))
