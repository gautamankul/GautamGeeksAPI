from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from .models import Profile
from .serializers import ProfileSerializer


# Create your views here.

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name = request.data.get("name", "").strip()
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        if not name or not username or not password:
            return Response(
                {"error": "name, username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Username already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Split full name into first and last name
        name_parts = name.split(maxsplit=1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Create user in the main Django User table
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        # Create profile linked to user
        Profile.objects.create(
            user=user,
            full_name=name,
        )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "message": "User registered successfully!",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "full_name": user.get_full_name(),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

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


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"detail": "refresh_token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(refresh_token)
            refresh.blacklist()

            return Response(
                {"message": "Logout successful"},
                status=status.HTTP_205_RESET_CONTENT,
            )

        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
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
