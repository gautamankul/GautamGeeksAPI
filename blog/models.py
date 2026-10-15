from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models

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

    def save(self, *args, **kwargs):
        self.is_published = True
        self.is_draft = False

        if not self.category_id and self.keywords:
            try:
                from .categorizers import predict_category
                self.category = predict_category(
                    self.keywords, self.created_by)
            except Exception as e:  # never block saving a post
                import logging
                logging.getLogger(__name__).exception(
                    "Auto-categorize failed: %s", e)

        super().save(*args, **kwargs)


class PostInteraction(models.Model):
    class Action(models.TextChoices):
        VIEW = "view", "View"
        LIKE = "like", "Like"
        SAVE = "save", "Save"
        SHARE = "share", "Share"
        CLAP = "clap", "Clap"
        DISMISS = "dismiss", "Not interested"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_interactions", )
    post = models.ForeignKey(
        "Post", on_delete=models.CASCADE, related_name="interactions", )
    action = models.CharField(max_length=10, choices=Action.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "action"]),
            models.Index(fields=["post", "action"]),
        ]

    def save(self, *args, **kwargs):
        if self.action == self.CLAP:
            clap_count = PostInteraction.objects.filter(
                user=self.user, post=self.post, action=self.CLAP
            ).count()
            if clap_count >= 100:
                raise ValidationError(
                    "You can clap a maximum of 100 times per post.")
        super().save(*args, **kwargs)


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


class StoryList(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="story_lists")
    # e.g., "Reading list", "Django Authentication"
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    is_private = models.BooleanField(default=True)
    stories = models.ManyToManyField(Post, related_name="in_lists", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} - {self.user.username}"


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
