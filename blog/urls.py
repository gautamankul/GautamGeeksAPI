from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import PostViewSet , UserPostViewSet ,PublicPostViewSet
from .views import ImageUploadView,TrendingPostView

# Routers 
router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')
router.register(r'public_posts', PublicPostViewSet, basename='public_posts')
router.register(r'user_posts', UserPostViewSet, basename='user_posts')


# Common URLS
urlpatterns = [
    path('', include(router.urls)),
    path('upload-image/', ImageUploadView.as_view(), name='upload_image'),
    path('trending-posts/', TrendingPostView.as_view(), name='trending_posts'),
]