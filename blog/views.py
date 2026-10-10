import os
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated

# Create your views here.
class ImageUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('image')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)

        # Save to media/uploads/
        file_path = default_storage.save(f"uploads/{file_obj.name}", file_obj)
        image_url = request.build_absolute_uri(settings.MEDIA_URL + file_path)

        return Response({'url': image_url})