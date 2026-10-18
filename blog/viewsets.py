from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets
from .models import Post
from .serializations import (UserPostViewSetSerializer, PublicPostViewSetSerializer)


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
        return Post.objects.filter(
            created_by=self.request.user
        ).select_related(
            "category", "created_by", "updated_by"
        )


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
