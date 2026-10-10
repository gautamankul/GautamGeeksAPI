import os
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from sentence_transformers import SentenceTransformer, util
from rest_framework import status

from .serializers import PostSerializer
from .models import Post
from .utils import get_trending_keywords, get_post_search_text
import logging

logger = logging.getLogger(__name__)


# Create your views here.
class ImageUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get("image")
        if not file_obj:
            return Response({"error": "No file provided"}, status=400)

        # Save to media/uploads/
        file_path = default_storage.save(f"uploads/{file_obj.name}", file_obj)
        image_url = request.build_absolute_uri(settings.MEDIA_URL + file_path)

        return Response({"url": image_url})


class TrendingPostView(APIView):
    permission_classes = [AllowAny]
    serializer_class = PostSerializer

    llm_model = SentenceTransformer("all-MiniLM-L6-v2")

    def get(self, request, *args, **kwargs):
        try:
            trending_keywords = get_trending_keywords()

            if not trending_keywords:
                return Response({
                    "trending_posts": [],
                    "message": "No trending keywords available.",
                })

            posts = list(
                Post.objects.filter(is_published=True)
                .select_related("category")
            )

            if not posts:
                return Response({"trending_posts": []})

            post_texts = [
                get_post_search_text(post)
                for post in posts
            ]

            valid_indices = [
                i for i, text in enumerate(post_texts) if text
            ]

            if not valid_indices:
                return Response({
                    "trending_posts": [],
                    "message": "No searchable post content found.",
                })

            valid_texts = [
                post_texts[i] for i in valid_indices
            ]

            keyword_embeddings = self.llm_model.encode(
                trending_keywords,
                convert_to_tensor=True,
                normalize_embeddings=True,
            )

            post_embeddings = self.llm_model.encode(
                valid_texts,
                convert_to_tensor=True,
                normalize_embeddings=True,
                batch_size=32,
            )

            similarities = util.cos_sim(
                post_embeddings, keyword_embeddings
            )

            threshold = 0.45
            matched_posts = []
            updated_posts = []

            for row, original_index in enumerate(valid_indices):
                post = posts[original_index]
                score = similarities[row].max().item()
                is_trending = score >= threshold

                if post.is_trending != is_trending:
                    post.is_trending = is_trending
                    updated_posts.append(post)

                if is_trending:
                    matched_posts.append((post, score))

            if updated_posts:
                Post.objects.bulk_update(
                    updated_posts,
                    ["is_trending"],
                    batch_size=100,
                )

            matched_posts.sort(
                key=lambda item: item[1],
                reverse=True,
            )

            trending_posts = [
                post for post, _ in matched_posts
            ]

            serializer = self.serializer_class(
                trending_posts,
                many=True,
                context={"request": request},
            )

            return Response({
                "trending_posts": serializer.data,
                "trending_keywords": trending_keywords,
                "total_trending_posts": len(trending_posts),
            })

        except Exception:
            logger.exception("Failed to fetch trending posts")

            return Response(
                {"error": "Unable to fetch trending posts."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
