from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
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
    HouseholdMemberSerializer,
    AddHouseholdMemberSerializer,
    UpdateHouseholdMemberSerializer,
)
from .models import (
    Household,
    HouseholdMembership,
    NotificationSettings,
    UserSettings,
)
from .permissions import IsHouseholdOwner
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

    def get_permissions(self):
        if self.action in (
            "update",
            "partial_update",
            "destroy",
        ):
            return [
                IsAuthenticated(),
                IsHouseholdOwner(),
            ]

        return [
            IsAuthenticated(),
        ]

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

@extend_schema(tags=["Household"])
class HouseholdMembersView(generics.ListCreateAPIView):
    serializer_class = HouseholdMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Получаем только участников запрошенного Household.
        #
        # select_related("user") позволяет сразу загрузить
        # связанного пользователя одним запросом к базе,
        # потому что сериализатор использует username.
        #
        # order_by("joined_at", "id") задаёт стабильный порядок
        # участников и предотвращает предупреждение пагинации
        # о непредсказуемом порядке QuerySet.
        return (
            HouseholdMembership.objects.filter(
                household_id=self.kwargs["household_id"]
            )
            .select_related("user")
            .order_by(
                "joined_at",
                "id",
            )
        )

    def get_serializer_class(self):
        # Для GET используем read-only сериализатор,
        # который возвращает user, username и role.
        if self.request.method == "GET":
            return HouseholdMemberSerializer

        # Для POST используем отдельный сериализатор,
        # который принимает user и role.
        return AddHouseholdMemberSerializer

    def list(self, request, *args, **kwargs):
        household_id = kwargs["household_id"]

        # Проверяем, является ли текущий пользователь
        # участником запрошенного Household.
        is_member = HouseholdMembership.objects.filter(
            household_id=household_id,
            user=request.user,
        ).exists()

        # Если пользователь не является участником Household,
        # запрещаем ему просматривать список участников.
        if not is_member:
            return Response(
                {
                    "detail": "You are not a member of this household."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Если пользователь является участником Household,
        # возвращаем список всех участников.
        return super().list(
            request,
            *args,
            **kwargs,
        )

    def create(self, request, *args, **kwargs):
        household_id = kwargs["household_id"]

        # Проверяем, является ли текущий пользователь OWNER
        # этого Household.
        #
        # Только OWNER имеет право добавлять новых участников.
        is_owner = HouseholdMembership.objects.filter(
            household_id=household_id,
            user=request.user,
            role=HouseholdMembership.Role.OWNER,
        ).exists()

        # ADULT, CHILD и пользователь, который не состоит
        # в Household, не могут добавлять участников.
        if not is_owner:
            return Response(
                {
                    "detail": (
                        "Only the household owner "
                        "can add members."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Получаем сам Household, чтобы передать его
        # в контекст сериализатора.
        household = Household.objects.get(
            pk=household_id
        )

        # Передаём Household в context, потому что сериализатор
        # должен проверить, не является ли добавляемый пользователь
        # уже участником именно этого Household.
        serializer = self.get_serializer(
            data=request.data,
            context={
                **self.get_serializer_context(),
                "household": household,
            },
        )

        # Проверяем входные данные.
        serializer.is_valid(raise_exception=True)

        # Создаём membership и связываем его
        # с текущим Household.
        membership = serializer.save(
            household=household,
        )

        # Возвращаем созданного участника.
        #
        # Для ответа используем обычный read-only сериализатор,
        # чтобы клиент получил также username.
        response_serializer = HouseholdMemberSerializer(
            membership,
            context=self.get_serializer_context(),
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Household"])
class HouseholdMemberDetailView(generics.UpdateAPIView):
    serializer_class = UpdateHouseholdMemberSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch"]

    def get_queryset(self):
        # Ограничиваем QuerySet участниками Household,
        # указанного в URL.
        #
        # Благодаря этому нельзя изменить участника
        # из другого Household через подстановку ID.
        return HouseholdMembership.objects.filter(
            household_id=self.kwargs["household_id"]
        ).select_related(
            "user",
            "household",
        )

    def get_object(self):
        # Получаем текущего пользователя.
        user = self.request.user

        # Получаем ID Household из URL.
        household_id = self.kwargs["household_id"]

        # Проверяем, является ли текущий пользователь
        # OWNER именно этого Household.
        is_owner = HouseholdMembership.objects.filter(
            household_id=household_id,
            user=user,
            role=HouseholdMembership.Role.OWNER,
        ).exists()

        # Только OWNER может изменять роли участников.
        if not is_owner:
            raise PermissionDenied(
                "Only the household owner can update members."
            )

        # Получаем участника из ограниченного QuerySet.
        #
        # Если участник не принадлежит этому Household,
        # будет возвращён ответ 404.
        return get_object_or_404(
            self.get_queryset(),
            pk=self.kwargs["member_id"],
        )

    def update(self, request, *args, **kwargs):
        # Получаем участника с проверкой прав OWNER.
        instance = self.get_object()

        # Для PATCH используем частичное обновление.
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True,
        )

        # Проверяем входные данные сериализатора.
        serializer.is_valid(raise_exception=True)

        # Сохраняем новую роль.
        self.perform_update(serializer)

        # Возвращаем обновлённые данные участника.
        response_serializer = HouseholdMemberSerializer(
            instance,
            context=self.get_serializer_context(),
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )