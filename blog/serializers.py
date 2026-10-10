from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Post, Category
from accounts.models import Profile

User = get_user_model()

# Create your serializers here.


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class ProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ["id", "full_name", "avatar", "avatar_url", "bio"]

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj.avatar and hasattr(obj.avatar, "url"):
            return request.build_absolute_uri(obj.avatar.url)
        return None


class PostSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    profile = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "content_json",
            "content_html",
            "category",
            "profile",
            'keywords',
            'is_paywalled',
            'notify_subscribers',
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
        ]

    def get_profile(self, obj):
        if hasattr(obj.created_by, "profile"):
            # Pass the parent serializer context so request is available
            return ProfileSerializer(obj.created_by.profile, context=self.context).data
        return None

    def validate_keywords(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Keywords must be a list of strings.")
        if len(value) > 5:
            raise serializers.ValidationError("You can add up to 5 topics only.")
        return [str(tag).strip() for tag in value if str(tag).strip()]
