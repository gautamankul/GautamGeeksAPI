from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Post, Series
from .serializations import (UserPostViewSetSerializer, PublicPostViewSetSerializer, SeriesViewSetSerializer)


class SeriesViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SeriesViewSetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Series.objects
            .filter(created_by=self.request.user)
            .prefetch_related('posts')
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=['get'], url_path='incomplete')
    def incomplete(self, request):
        series = self.get_queryset().filter(is_completed=False)
        serializer = self.get_serializer(series, many=True)
        return Response(serializer.data)


class PostViewSet(viewsets.ModelViewSet):
    serializer_class = UserPostViewSetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Post.objects.filter(
            created_by=self.request.user
        ).select_related(
            "category", "created_by", "updated_by"
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class UserPostViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserPostViewSetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Post.objects
            .filter(created_by=self.request.user)
            .select_related(
                "series",
                "category",
                "created_by",
                "updated_by",
            )
        )

    @action(detail=False, methods=["get"], url_path="standalone_posts")
    def standalone_posts(self, request):
        """
        Return posts that do not belong to any series.
        """
        posts = self.get_queryset().filter(series__isnull=True)

        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path=r"by-series/(?P<series_id>\d+)", )
    def posts_by_series(self, request, series_id=None):
        """
        Return posts belonging to a specific series.
        """
        posts = self.get_queryset().filter(series_id=series_id)

        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)


class PublicPostViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PublicPostViewSetSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Post.objects.filter(
            is_published=True,
            is_draft=False,
        ).select_related(
            "category", "created_by", "updated_by"
        ).order_by("-created_at")

        category_name = self.request.query_params.get("category")

        if category_name:
            queryset = queryset.filter(
                category__name__iexact=category_name
            )

        if self.action == "list":
            return queryset[:5]

        return queryset
