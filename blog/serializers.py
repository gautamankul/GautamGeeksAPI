from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Sum

from .models import Post, Category, StoryList, PostClap, PostComment, Follow
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
        fields = "__all__"


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


class PostClapSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostClap
        fields = '__all__'


class PostCommentSerializer(serializers.ModelSerializer):
    profile = BProfileSerializer(source="user.profile", read_only=True)

    class Meta:
        model = PostComment
        exclude = ['post']
        depth = 1


class StoryListSerializer(serializers.ModelSerializer):
    story_count = serializers.SerializerMethodField()
    thumbnails = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source="user.profile.full_name",read_only=True,default="Anonymous")
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
            "stories",
            "created_at",
            "updated_at",
        ]
        depth = 1

    def get_story_count(self, obj):
        return obj.stories.count()

    def get_thumbnails(self, obj):
        request = self.context.get("request")
        images = []

        for post in obj.stories.all()[:3]:
            if post.preview_image:
                url = post.preview_image.url
                if request:
                    url = request.build_absolute_uri(url)
                images.append(url)

        return images

    def get_creator_avatar(self, obj):
        profile = getattr(obj.user, "profile", None)

        if profile and profile.avatar:
            url = profile.avatar.url
            request = self.context.get("request")

            if request:
                return request.build_absolute_uri(url)

            return url

        return None


class StoryListBookmarkSerializer(serializers.ModelSerializer):
    contains_story = serializers.SerializerMethodField()

    class Meta:
        model = StoryList
        fields = ["id", "name", "is_private", "contains_story"]

    def get_contains_story(self, obj):
        story_id = self.context.get("post_id")

        if not story_id:
            return False

        return obj.stories.filter(id=story_id).exists()


class StoryListToggleStorySerializer(serializers.Serializer):
    story_id = serializers.IntegerField(required=True)


class FollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Follow
        fields = "__all__"
        read_only_fields = ["id", "follower", "created_at"]


class PostSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    profile = serializers.SerializerMethodField()
    total_claps = serializers.SerializerMethodField()
    my_claps = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

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
            'is_following',
            'comment_count',
            'is_paywalled',
            'notify_subscribers',
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
        return obj.clap.aggregate(total=Sum("clap_count"))["total"] or 0

    def get_my_claps(self, obj):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return 0

        return PostClap.objects.filter(post=obj, user=request.user).aggregate(total=Sum("clap_count"))["total"] or 0

    def get_is_following(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        # Users cannot follow themselves
        if request.user == obj.created_by:
            return False

        return Follow.objects.filter(
            follower=request.user,
            following=obj.created_by
        ).exists()

    def get_comment_count(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0

        return PostComment.objects.filter(post=obj).count()
