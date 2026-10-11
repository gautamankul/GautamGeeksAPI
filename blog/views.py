import os
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from sentence_transformers import SentenceTransformer, util
from rest_framework import status
from django.utils import timezone
from datetime import datetime, date
from django.db.models import Sum
import calendar

from .serializers import *
from .models import *
from .utils import *
import logging
import math

logger = logging.getLogger(__name__)


# Create your views here.
class ImageUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get("image")
        if not file_obj:
            return Response({"error": "No file provided"}, status=400)

        # Save to media/uploads/
        file_path = default_storage.save(f"uploads/{file_obj.name}", file_obj)
        image_url = request.build_absolute_uri(settings.MEDIA_URL + file_path)

        return Response({"url": image_url})


class TrendingPostViewOLd(APIView):
    permission_classes = [AllowAny]
    serializer_class = PostSerializer

    llm_model = SentenceTransformer("all-MiniLM-L6-v2")

    def get(self, request, *args, **kwargs):
        try:
            trending_keywords = get_trending_keywords()

            if not trending_keywords:
                return Response({
                    "trending_posts": [],
                    "message": "No trending keywords available.",
                })

            posts = list(
                Post.objects.filter(is_published=True)
                .select_related("category")
            )

            if not posts:
                return Response({"trending_posts": []})

            post_texts = [
                get_post_search_text(post)
                for post in posts
            ]

            valid_indices = [
                i for i, text in enumerate(post_texts) if text
            ]

            if not valid_indices:
                return Response({
                    "trending_posts": [],
                    "message": "No searchable post content found.",
                })

            valid_texts = [
                post_texts[i] for i in valid_indices
            ]

            keyword_embeddings = self.llm_model.encode(
                trending_keywords,
                convert_to_tensor=True,
                normalize_embeddings=True,
            )

            post_embeddings = self.llm_model.encode(
                valid_texts,
                convert_to_tensor=True,
                normalize_embeddings=True,
                batch_size=32,
            )

            similarities = util.cos_sim(
                post_embeddings, keyword_embeddings
            )

            threshold = 0.45
            matched_posts = []
            updated_posts = []

            for row, original_index in enumerate(valid_indices):
                post = posts[original_index]
                score = similarities[row].max().item()
                is_trending = score >= threshold

                if post.is_trending != is_trending:
                    post.is_trending = is_trending
                    updated_posts.append(post)

                if is_trending:
                    matched_posts.append((post, score))

            if updated_posts:
                Post.objects.bulk_update(
                    updated_posts,
                    ["is_trending"],
                    batch_size=100,
                )

            matched_posts.sort(
                key=lambda item: item[1],
                reverse=True,
            )

            trending_posts = [
                post for post, _ in matched_posts
            ]

            serializer = self.serializer_class(
                trending_posts,
                many=True,
                context={"request": request},
            )

            return Response({
                "trending_posts": serializer.data,
                "trending_keywords": trending_keywords,
                "total_trending_posts": len(trending_posts),
            })

        except Exception:
            logger.exception("Failed to fetch trending posts")

            return Response(
                {"error": "Unable to fetch trending posts."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class TrendingPostView(APIView):
    permission_classes = [AllowAny]
    serializer_class = PostSerializer

    llm_model = SentenceTransformer("all-MiniLM-L6-v2")

    def compute_score(self, post, similarity_score: float) -> float:
        """Composite trending score: engagement + freshness + topic similarity"""
        age_hours = (timezone.now() - post.created_at).total_seconds() / 3600

        views = getattr(post, "views", 0)
        claps = getattr(post, "claps", 0)
        comments = getattr(post, "comments_count", 0)

        # Weights (tune these based on your app’s needs)
        alpha, beta, gamma, delta = 1.0, 2.0, 3.0, 5.0

        score = (
                (alpha * views) / (1 + math.log(1 + age_hours)) +
                (beta * claps) / math.sqrt(1 + age_hours) +
                (gamma * comments) / math.sqrt(1 + age_hours) +
                (delta * similarity_score)
        )
        return score

    def get(self, request, *args, **kwargs):
        try:
            trending_keywords = get_trending_keywords()

            if not trending_keywords:
                return Response({
                    "trending_posts": [],
                    "message": "No trending keywords available.",
                })

            posts = list(Post.objects.filter(is_published=True).select_related("category"))

            if not posts:
                return Response({"trending_posts": []})

            post_texts = [get_post_search_text(post) for post in posts]
            valid_indices = [i for i, text in enumerate(post_texts) if text]

            if not valid_indices:
                return Response({
                    "trending_posts": [],
                    "message": "No searchable post content found.",
                })

            valid_texts = [post_texts[i] for i in valid_indices]

            keyword_embeddings = self.llm_model.encode(
                trending_keywords,
                convert_to_tensor=True,
                normalize_embeddings=True,
            )

            post_embeddings = self.llm_model.encode(
                valid_texts,
                convert_to_tensor=True,
                normalize_embeddings=True,
                batch_size=32,
            )

            similarities = util.cos_sim(post_embeddings, keyword_embeddings)

            matched_posts = []
            updated_posts = []

            for row, original_index in enumerate(valid_indices):
                post = posts[original_index]
                similarity_score = similarities[row].max().item()
                score = self.compute_score(post, similarity_score)

                is_trending = score >= 10  # threshold for trending
                if post.is_trending != is_trending:
                    post.is_trending = is_trending
                    updated_posts.append(post)

                if is_trending:
                    matched_posts.append((post, score))

            if updated_posts:
                Post.objects.bulk_update(updated_posts, ["is_trending"], batch_size=100)

            matched_posts.sort(key=lambda item: item[1], reverse=True)
            trending_posts = [post for post, _ in matched_posts[:10]]  # top 10

            serializer = self.serializer_class(trending_posts, many=True, context={"request": request})

            return Response({
                "trending_posts": serializer.data,
                "trending_keywords": trending_keywords,
                "total_trending_posts": len(trending_posts),
            })

        except Exception:
            logger.exception("Failed to fetch trending posts")
            return Response(
                {"error": "Unable to fetch trending posts."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class PostInteractionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InteractionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        post_id = serializer.validated_data["post_id"]
        action = serializer.validated_data["action"]

        post = Post.objects.filter(
            id=post_id,
            is_published=True,
            is_draft=False,
        ).first()

        if post is None:
            return Response(
                {"detail": "Post not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Add paywall/subscription authorization here.
        # Rate-limit view events and deduplicate repeated views.
        PostInteraction.objects.create(
            user=request.user,
            post=post,
            action=action,
        )

        return Response(
            {"detail": "Interaction recorded."},
            status=status.HTTP_201_CREATED,
        )


class MonthlyStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        today = date.today()

        # Parse query params (defaults to current month/year)
        month = int(request.query_params.get('month', today.month))
        year = int(request.query_params.get('year', today.year))

        num_days = calendar.monthrange(year, month)[1]
        start_date = date(year, month, 1)
        end_date = date(year, month, num_days)

        # Query all daily stats belonging to stories written by this user
        stats_qs = PostDailyStat.objects.filter(
            post__created_by=user,
            date__gte=start_date,
            date__lte=end_date
        )

        # Aggregate monthly totals
        totals = stats_qs.aggregate(
            total_presentations=Sum('presentations'),
            total_views=Sum('views'),
            total_reads=Sum('reads')
        )

        # Group stats by day
        day_map = {
            row['date']: row
            for row in stats_qs.values('date').annotate(
                views=Sum('views'),
                reads=Sum('reads'),
                presentations=Sum('presentations')
            )
        }

        # Build complete daily series for charting
        chart_data = []
        for day in range(1, num_days + 1):
            curr_date = date(year, month, day)
            curr_entry = day_map.get(curr_date, {})
            chart_data.append({
                "day": day,
                "date": curr_date.strftime("%b %d"),
                "views": curr_entry.get("views", 0),
                "reads": curr_entry.get("reads", 0),
                "presentations": curr_entry.get("presentations", 0),
            })

        # Followers & Email Subscribers count
        followers_count = getattr(user, 'followers', None)
        followers_count = followers_count.count() if followers_count else 0

        subscribers_count = getattr(user, 'email_subscribers', None)
        subscribers_count = subscribers_count.count() if subscribers_count else 0

        return Response({
            "month": month,
            "year": year,
            "date_range": f"{start_date.strftime('%B %d, %Y')} – {'Today' if month == today.month and year == today.year else end_date.strftime('%B %d, %Y')} (UTC)",
            "summary": {
                "presentations": totals['total_presentations'] or 0,
                "views": totals['total_views'] or 0,
                "reads": totals['total_reads'] or 0,
                "followers": followers_count,
                "subscribers": subscribers_count,
            },
            "chart_data": chart_data,
        })
