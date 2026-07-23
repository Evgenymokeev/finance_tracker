from rest_framework import generics

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from drf_spectacular.utils import extend_schema

from .serializers import RegisterSerializer
from rest_framework.permissions import AllowAny

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