from django.db.models import Count, Case, When, IntegerField
from .models import Category, Post


def get_user_top_categories(user, limit=3):
    """Categories the user writes in most, with post counts."""
    return (
        Category.objects
        .filter(posts__created_by=user)
        .annotate(post_count=Count("posts"))
        .order_by("-post_count")[:limit]
    )


def get_recommended_posts(user, limit_categories=3):
    top = list(get_user_top_categories(user, limit_categories))
    qs = (
        Post.objects
        .filter(is_published=True)
        .exclude(created_by=user)
        .select_related("category", "created_by")
    )

    # New user with no posts -> fall back to trending
    if not top:
        return qs.order_by("-is_trending", "-created_at")

    # Rank by how much the user writes in that category
    weights = Case(
        *[When(category_id=c.id, then=len(top) - i) for i, c in enumerate(top)],
        default=0,
        output_field=IntegerField(),
    )

    return (
        qs.filter(category__in=[c.id for c in top])
        .annotate(rank=weights)
        .order_by("-rank", "-is_trending", "-created_at")
    )

