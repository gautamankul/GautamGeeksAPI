from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import PostViewSet, UserPostViewSet, PublicPostViewSet ,SeriesViewSet
from .views import *

# Routers 
router = DefaultRouter()
router.register(r'series', SeriesViewSet, basename='series')
router.register(r'posts', PostViewSet, basename='post')
router.register(r'public_posts', PublicPostViewSet, basename='public_posts')
router.register(r'user_posts', UserPostViewSet, basename='user_posts')

# Common URLS
urlpatterns = [
    path('', include(router.urls)),
    path('upload-image/', ImageUploadView.as_view(), name='upload_image'),
    path('monthly-stats/', MonthlyStatsView.as_view(), name='monthly_stats'),
    path("my-recommended/", MyRecommendedPostsView.as_view()),
    path("my-features/", MyFeaturesPostView.as_view()),
    path("detail-story/<int:pk>/", BlogPostDetailAPIView.as_view(), name="blog-post-detail", ),
    path("clap/<int:post_id>/", PostClapAPIView.as_view(), name="post-clap", ),
    path("comments/<int:post_id>/", PostCommentAPIView.as_view(), name="post-comment", ),
    path("comments-list/<int:post_id>/", PostCommentListAPIView.as_view(), name="post-comment-list", ),
    path('follow/', FollowUserView.as_view(), name='follow-user'),
    path('followers-list/<int:user_id>/', FollowerListView.as_view(), name='followers-list'),
    path("story-lists/create/", StoryListCreateAPIView.as_view(), name="story-list-create"),
    path("story-lists/", StoryListAPIView.as_view(), name="story-list"),
    path("story-lists/<int:pk>/", StoryListDetailAPIView.as_view(), name="story-list-detail"),
    path("story-lists/<int:pk>/delete/", StoryListDeleteAPIView.as_view(), name="story-list-delete"),
]
