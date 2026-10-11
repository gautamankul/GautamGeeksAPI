from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets
from .models import Post, StoryList
from .serializers import PostSerializer, StoryListSerializer


# Create your views here.
class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class UserPostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Post.objects.filter(created_by=self.request.user)


class PublicPostViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [AllowAny]  # No login required

    def get_queryset(self):
        queryset = Post.objects.filter(is_published=True).order_by('-created_at')

        # ✅ Filter by category name if provided
        category_name = self.request.query_params.get('category')
        if category_name:
            queryset = queryset.filter(category__name__iexact=category_name)

        # ✅ Limit to latest 5 posts for list view
        if self.action == 'list':
            return queryset[:5]

        return queryset

    def get_serializer_context(self):
        # 🔑 This ensures request is available inside serializers
        return {"request": self.request}


class StoryListViewSet(viewsets.ModelViewSet):
    serializer_class = StoryListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return StoryList.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
