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
    UserSettingsSerializer,
    NotificationSettingsSerializer,
    HouseholdSerializer,
)
from .models import (
    Household,
    HouseholdMembership,
    NotificationSettings,
    UserSettings,
)
from rest_framework import generics, status, viewsets


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

@extend_schema(tags=["Settings"])
class UserSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        settings, created = UserSettings.objects.get_or_create(
            user=self.request.user
        )

        return settings

@extend_schema(tags=["Settings"])
class NotificationSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = NotificationSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        settings, created = NotificationSettings.objects.get_or_create(
            user=self.request.user
        )

        return settings


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


@extend_schema(tags=["Household"])
class HouseholdViewSet(viewsets.ModelViewSet):
    serializer_class = HouseholdSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Household.objects.filter(
            memberships__user=self.request.user
        ).distinct()

    def perform_create(self, serializer):
        household = serializer.save(
            created_by=self.request.user
        )

        HouseholdMembership.objects.create(
            household=household,
            user=self.request.user,
            role=HouseholdMembership.Role.OWNER,
        )