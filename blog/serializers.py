from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Post, Category, StoryList, PostInteraction
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


class BProfileSerializer(serializers.ModelSerializer):
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
            'keywords',
            'is_paywalled',
            'notify_subscribers',
            "total_claps",
            "my_claps"
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
            return BProfileSerializer(obj.created_by.profile, context=self.context).data
        return None

    def validate_keywords(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Keywords must be a list of strings.")
        if len(value) > 5:
            raise serializers.ValidationError("You can add up to 5 topics only.")
        return [str(tag).strip() for tag in value if str(tag).strip()]

    def get_total_claps(self, obj):
        return obj.interactions.filter(action="clap").count()

    def get_my_claps(self, obj):
        user = self.context["request"].user
        return obj.interactions.filter(action="clap", user=user).count()


class InteractionInputSerializer(serializers.Serializer):
    post_id = serializers.IntegerField()
    action = serializers.ChoiceField(
        choices=PostInteraction.Action.choices
    )


class StoryListSerializer(serializers.ModelSerializer):
    story_count = serializers.IntegerField(source="stories.count", read_only=True)
    thumbnails = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source="user.profile.full_name", default="Anonymous")
    creator_avatar = serializers.SerializerMethodField()

    class Meta:
        model = StoryList
        fields = [
            "id",
            "name",
            "description",
            "is_private",
            "story_count",
            "thumbnails",
            "creator_name",
            "creator_avatar",
            "created_at",
            "updated_at",
        ]

    def get_thumbnails(self, obj):
        # Gather up to 3 story preview images for the card stack
        images = []
        for post in obj.stories.all()[:3]:
            if post.preview_image:
                images.append(post.preview_image)
        return images

    def get_creator_avatar(self, obj):
        if hasattr(obj.user, 'profile') and obj.user.profile.avatar:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.user.profile.avatar.url) if request else obj.user.profile.avatar.url
        return None
