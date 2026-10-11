from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Profile
from .serializers import ProfileSerializer


# Create your views here.
class RegisterView(APIView):
    def post(self, request):
        name = request.data.get("name")
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password or not name:
            return Response(
                {"error": "full_name, username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Username already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create user
        user = User.objects.create_user(username=username, password=password)

        # Create profile linked to user
        Profile.objects.create(user=user, full_name=name)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "message": "User registered successfully!",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(username=username, password=password)

        if user is not None:
            refresh = RefreshToken.for_user(user)

            # Get profile details if available
            profile = getattr(user, "profile", None)
            full_name = profile.full_name if profile else ""
            avatar_url = None
            if profile and profile.avatar:
                # Build absolute URL for avatar
                avatar_url = request.build_absolute_uri(profile.avatar.url)

            return Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "message": "Signed in successfully!",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "full_name": full_name,
                        "avatar_url": avatar_url,
                    },
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"error": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = ProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)

        # Handle avatar removal
        if request.data.get('remove_avatar') == 'true':
            if profile.avatar:
                profile.avatar.delete(save=False)
            profile.avatar = None

        serializer = ProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
