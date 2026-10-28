from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from rest_framework import status
from django.db import transaction
from datetime import date

from .recommendations import *
from .serializers import *
from .models import *

import calendar
import logging

MAX_CLAPS = 100
MAX_CLAPS_PER_POST = 100
MAX_COMMENTS_PER_POST = 5

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


class MyRecommendedPostsView(generics.ListAPIView):
    """ This is for logged user you post for recommended posts """

    permission_classes = [IsAuthenticated]
    serializer_class = PostSerializer

    def get_queryset(self):
        print('get_recommended_posts', get_recommended_posts(self.request.user))
        return get_recommended_posts(self.request.user)


class MyFeaturesPostView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        base = (
            Post.objects
            .filter(is_published=True)
            .exclude(created_by=user)
            .select_related("category", "created_by")
        )

        # Get categories from posts written by the user
        top_categories = (
            Post.objects
            .filter(created_by=user)
            .values_list("category_id", flat=True)
            .distinct()
        )

        # If the user has not written any posts,
        # return 5 random published posts
        if not top_categories.exists():
            posts = list(base.order_by("-id")[:5])

        else:
            # Fetch 5 random posts from the user's categories
            posts = list(base.filter(category_id__in=top_categories).order_by("-id")[:5])

            # If fewer than 5 were found, fill with ran dom posts
            if len(posts) < 5:
                selected_ids = [post.id for post in posts]

                remaining_posts = base.exclude(
                    id__in=selected_ids
                ).order_by("-id")[:5 - len(posts)]

                posts.extend(remaining_posts)

        serializer = PostSerializer(
            posts[:5],
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)


class BlogPostDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        post = get_object_or_404(
            Post.objects.select_related("category", "created_by", "updated_by", ),
            pk=pk,
            is_published=True,
            is_draft=False,
        )

        serializer = PostSerializer(post, context={"request": request}, )
        return Response(serializer.data)


class PostClapAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        try:
            post = Post.objects.get(
                id=post_id,
                is_published=True,
                is_draft=False,
            )
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            with transaction.atomic():
                clap, created = PostClap.objects.get_or_create(
                    user=request.user,
                    post=post,
                    defaults={"clap_count": 0},
                )

                # Lock the row to prevent concurrent requests
                # from exceeding the limit.
                clap = PostClap.objects.select_for_update().get(
                    pk=clap.pk
                )

                if clap.clap_count >= MAX_CLAPS_PER_POST:
                    return Response(
                        {
                            "error": "You can clap a post up to 100 times.",
                            "clap_count": clap.clap_count,
                            "max_claps": MAX_CLAPS_PER_POST,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                clap.clap_count += 1
                clap.save(update_fields=["clap_count"])

        except Exception:
            raise

        total_claps = PostClap.objects.filter(
            post=post
        ).aggregate(total=Sum("clap_count"))["total"] or 0

        return Response(
            {
                "message": "Clap added successfully.",
                "your_claps": clap.clap_count,
                "total_claps": total_claps,
                "max_claps": MAX_CLAPS_PER_POST,
            },
            status=status.HTTP_200_OK,
        )


class PostCommentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        comment_text = request.data.get("comment", "").strip()

        if not comment_text:
            return Response(
                {"error": "Comment cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            post = Post.objects.get(
                id=post_id,
                is_published=True,
                is_draft=False,
            )
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        with transaction.atomic():
            # Serialize comment creation for this post/user.
            Post.objects.select_for_update().get(pk=post.pk)

            comment_count = PostComment.objects.filter(
                user=request.user,
                post=post,
            ).count()

            if comment_count >= MAX_COMMENTS_PER_POST:
                return Response(
                    {
                        "error": "You can comment on a post up to 5 times.",
                        "your_comments": comment_count,
                        "max_comments": MAX_COMMENTS_PER_POST,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            comment = PostComment.objects.create(
                user=request.user,
                post=post,
                comment=comment_text,
            )

        return Response(
            {
                "message": "Comment added successfully.",
                "comment": {
                    "id": comment.id,
                    "comment": comment.comment,
                    "created_at": comment.created_at,
                },
                "your_comments": comment_count + 1,
                "max_comments": MAX_COMMENTS_PER_POST,
            },
            status=status.HTTP_201_CREATED,
        )


class PostCommentListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, post_id):
        comments = PostComment.objects.filter(
            post_id=post_id
        ).select_related("user").order_by("-created_at")

        serializer = PostCommentSerializer(
            comments,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=status.HTTP_200_OK)


class FollowUserView(generics.CreateAPIView):
    queryset = Follow.objects.all()
    serializer_class = FollowSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        following_user = serializer.validated_data.get('following')
        follower_user = self.request.user

        # Prevent following yourself
        if follower_user == following_user:
            raise ValidationError({
                "detail": "You cannot follow yourself."
            })

        # Check if already following
        if Follow.objects.filter(follower=follower_user, following=following_user).exists():
            raise ValidationError({
                "detail": "You are already following this user."
            })

        # Create the follow relationship
        serializer.save(follower=follower_user)


class FollowerListView(generics.ListAPIView):
    serializer_class = FollowSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        return Follow.objects.filter(following_id=user_id)


class UnfollowUserView(generics.DestroyAPIView):
    queryset = Follow.objects.all()
    permission_classes = [IsAuthenticated]

    def get_object(self):
        following_id = self.kwargs.get('user_id')
        # Find the follow object where current user follows target user
        return Follow.objects.get(follower=self.request.user, following_id=following_id)


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
