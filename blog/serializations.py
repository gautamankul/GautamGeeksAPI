from django.contrib.auth import get_user_model
from django.db.models import Sum
from rest_framework import serializers

from accounts.models import Profile
from .models import Post, Category, PostClap, PostComment

User = get_user_model()


class CategoryViewSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class UserViewSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class ProfileViewSetSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ["id", "full_name", "avatar", "avatar_url", "bio"]

    def get_avatar_url(self, obj):
        request = self.context.get("request")

        if obj.avatar and hasattr(obj.avatar, "url"):
            url = obj.avatar.url
            return request.build_absolute_uri(url) if request else url

        return None


class PostCommentSerializer(serializers.ModelSerializer):
    user = UserViewSetSerializer(read_only=True)

    class Meta:
        model = PostComment
        fields = ["id", "user", "comment", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class PublicPostViewSetSerializer(serializers.ModelSerializer):
    category = CategoryViewSetSerializer(read_only=True)
    created_by = UserViewSetSerializer(read_only=True)
    updated_by = UserViewSetSerializer(read_only=True)
    profile = serializers.SerializerMethodField()
    clap_count = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "content_json",
            "content_html",
            "category",
            "profile",
            "keywords",
            "is_paywalled",
            "notify_subscribers",
            "clap_count",
            "comments",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_keywords(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Keywords must be a list of strings."
            )

        if len(value) > 5:
            raise serializers.ValidationError(
                "You can add up to 5 topics only."
            )

        if not all(isinstance(tag, str) for tag in value):
            raise serializers.ValidationError(
                "Each keyword must be a string."
            )

        return [tag.strip() for tag in value if tag.strip()]

    def get_profile(self, obj):
        try:
            profile = obj.created_by.profile
        except Profile.DoesNotExist:
            return None

        return ProfileViewSetSerializer(
            profile, context=self.context
        ).data

    def get_clap_count(self, obj):
        return (
                PostClap.objects.filter(post=obj).aggregate(
                    total=Sum("clap_count")
                )["total"] or 0
        )

    def get_comments(self, obj):
        comments = PostComment.objects.filter(
            post=obj
        ).select_related("user").order_by("-created_at")

        return PostCommentSerializer(
            comments,
            many=True,
            context=self.context,
        ).data


class UserPostViewSetSerializer(serializers.ModelSerializer):
    category = CategoryViewSetSerializer(read_only=True)
    created_by = UserViewSetSerializer(read_only=True)
    updated_by = UserViewSetSerializer(read_only=True)
    profile = serializers.SerializerMethodField()
    total_claps = serializers.SerializerMethodField()
    my_claps = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "content_json",
            "content_html",
            "category",
            "profile",
            "keywords",
            "is_paywalled",
            "notify_subscribers",
            "total_claps",
            "my_claps",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "total_claps",
            "my_claps",
            "profile",
        ]

    def validate_keywords(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Keywords must be a list of strings."
            )

        if len(value) > 5:
            raise serializers.ValidationError(
                "You can add up to 5 topics only."
            )

        if not all(isinstance(tag, str) for tag in value):
            raise serializers.ValidationError(
                "Each keyword must be a string."
            )

        return [tag.strip() for tag in value if tag.strip()]

    def get_profile(self, obj):
        try:
            profile = obj.created_by.profile
        except Profile.DoesNotExist:
            return None

        return ProfileViewSetSerializer(
            profile, context=self.context
        ).data

    def get_total_claps(self, obj):
        return (
                PostClap.objects.filter(post=obj).aggregate(
                    total=Sum("clap_count")
                )["total"] or 0
        )

    def get_my_claps(self, obj):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return 0

        clap = PostClap.objects.filter(
            post=obj,
            user=request.user,
        ).first()

        return clap.clap_count if clap else 0
