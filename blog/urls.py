from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import PostViewSet , UserPostViewSet ,PublicPostViewSet ,StoryListViewSet
from .views import ImageUploadView, MonthlyStatsView , MyRecommendedPostsView ,MyFeaturesPostView

# Routers 
router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')
router.register(r'public_posts', PublicPostViewSet, basename='public_posts')
router.register(r'user_posts', UserPostViewSet, basename='user_posts')
router.register(r'story_lists', StoryListViewSet, basename='story_lists')


# Common URLS
urlpatterns = [
    path('', include(router.urls)),
    path('upload-image/', ImageUploadView.as_view(), name='upload_image'),
    path('monthly-stats/', MonthlyStatsView.as_view(), name='monthly_stats'),
    path("my-recommended/", MyRecommendedPostsView.as_view()),
    path("my-features/", MyFeaturesPostView.as_view()),
]