from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from urllib.parse import urlparse
from django.db import models
from django.conf import settings
import logging
import requests

User = get_user_model()


# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='category_created')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='category_updated')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name or f"Untitled Category #{self.id}"


class Post(models.Model):
    title = models.CharField(max_length=255, blank=True, default='')
    preview_image = models.ImageField(upload_to='post_previews', blank=True, default='')
    content_json = models.JSONField(null=True, blank=True)
    content_html = models.TextField(blank=True, default='')
    is_draft = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)
    keywords = models.JSONField(default=list, blank=True)
    is_paywalled = models.BooleanField(default=False)
    notify_subscribers = models.BooleanField(default=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='posts_created')
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts_updated')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"Untitled Post #{self.id}"

    def get_first_image_url(self, data):
        """Recursively find the first image URL in content_json."""
        if isinstance(data, dict):
            # Common image URL keys used by rich-text editors
            for key in ('src', 'url', 'image_url'):
                value = data.get(key)
                if isinstance(value, str) and value:
                    if key == 'src' or key == 'image_url':
                        return value
                    if data.get('type') in ('image', 'img'):
                        return value

            # Check whether this node represents an image
            if data.get('type') in ('image', 'img'):
                for key in ('src', 'url', 'image_url'):
                    value = data.get(key)
                    if isinstance(value, str) and value:
                        return value

            # Search nested objects and lists
            for value in data.values():
                result = self.get_first_image_url(value)
                if result:
                    return result

        elif isinstance(data, list):
            for item in data:
                result = self.get_first_image_url(item)
                if result:
                    return result

        return None

    def save(self, *args, **kwargs):
        self.is_published = True
        self.is_draft = False

        # Extract the first image from content_json
        image_url = self.get_first_image_url(self.content_json)

        if image_url:
            # Only download the image if preview_image isn't already
            # pointing to the same image.
            try:
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()

                filename = urlparse(image_url).path.split('/')[-1]
                if not filename:
                    filename = 'preview.jpg'

                self.preview_image.save(
                    filename,
                    ContentFile(response.content),
                    save=False,
                )
            except Exception:
                logging.getLogger(__name__).exception(
                    "Failed to download preview image: %s", image_url
                )
        else:
            self.preview_image = ''

        if not self.category_id and self.keywords:
            try:
                from .categorizers import predict_category
                self.category = predict_category(
                    self.keywords, self.created_by
                )
            except Exception as e:
                logging.getLogger(__name__).exception(
                    "Auto-categorize failed: %s", e
                )

        super().save(*args, **kwargs)


class PostClap(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_clap", )
    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name="clap", )
    clap_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "post")
        ordering = ['-created_at']


class PostComment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_comments", )
    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name="post_comments", )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class StoryList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="story_lists")
    stories = models.ManyToManyField(Post, related_name="in_lists", blank=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    is_private = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} - {self.user.username}"


class PostDailyStat(models.Model):
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name='daily_stats')
    date = models.DateField(db_index=True)
    presentations = models.PositiveIntegerField(
        default=0)  # Impressions in feeds
    views = models.PositiveIntegerField(default=0)  # Story page clicks
    reads = models.PositiveIntegerField(
        default=0)  # Readers who spent reading time

    class Meta:
        unique_together = ('post', 'date')
        ordering = ['date']

    def __str__(self):
        return f"{self.post.title} - {self.date}"


class Follow(models.Model):
    follower = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='following_set')
    following = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='follower_set')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')


class EmailSubscriber(models.Model):
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='email_subscriber_set')
    subscriber = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='subscribed_author_set')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('author', 'subscriber')
