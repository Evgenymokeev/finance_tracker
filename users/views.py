from rest_framework import generics

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from drf_spectacular.utils import extend_schema

from .serializers import RegisterSerializer


@extend_schema(
    tags=["Auth"]
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer


@extend_schema(
    tags=["Auth"]
)
class LoginView(TokenObtainPairView):
    pass


@extend_schema(
    tags=["Auth"]
)
class RefreshView(TokenRefreshView):
    pass