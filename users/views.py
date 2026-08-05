from django.contrib.auth import update_session_auth_hash

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from drf_spectacular.utils import extend_schema

from .serializers import (
    RegisterSerializer,
    ProfileSerializer,
    ChangePasswordSerializer,
)


@extend_schema(tags=["Auth"])
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


@extend_schema(tags=["Auth"])
class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]


@extend_schema(tags=["Auth"])
class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]


@extend_schema(tags=["Profile"])
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


@extend_schema(tags=["Profile"])
class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        if not user.check_password(
            serializer.validated_data["old_password"]
        ):
            return Response(
                {
                    "old_password": [
                        "Current password is incorrect."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(
            serializer.validated_data["new_password"]
        )
        user.save()

        update_session_auth_hash(request, user)

        return Response(
            {
                "detail": "Password changed successfully."
            },
            status=status.HTTP_200_OK,
        )