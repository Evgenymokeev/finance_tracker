from django.conf import settings
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from drf_spectacular.utils import extend_schema

from rest_framework import generics, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .models import (
    Household,
    HouseholdMembership,
    NotificationSettings,
    UserSettings,
)

from .permissions import IsHouseholdOwner

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
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)


User = get_user_model()


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

@extend_schema(tags=["Auth"])
class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            reset_url = (
                "http://localhost:8000/api/v1/auth/"
                f"password-reset-confirm/?uid={uid}&token={token}"
            )

            send_mail(
                subject="Password reset",
                message=(
                    "You requested a password reset.\n\n"
                    "Use the following link to reset your password:\n\n"
                    f"{reset_url}\n\n"
                    "If you did not request this, you can ignore this email."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

        return Response(
            {
                "detail": (
                    "If an account with this email exists, "
                    "a password reset link has been sent."
                )
            },
            status=status.HTTP_200_OK,
        )

@extend_schema(tags=["Auth"])
class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        # Получаем uid и token напрямую из запроса.
        #
        # Пока мы не запускаем полную валидацию serializer,
        # потому что сначала должны определить пользователя.
        uid = request.data.get("uid")
        token = request.data.get("token")

        # Проверяем, что uid и token вообще переданы.
        #
        # Если одного из них нет, ссылка для восстановления
        # считается недействительной.
        if not uid or not token:
            return Response(
                {
                    "detail": "Invalid password reset link."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Декодируем uid, который Django создал
            # при отправке письма.
            user_id = force_str(
                urlsafe_base64_decode(uid)
            )

            # Находим активного пользователя.
            user = User.objects.get(
                pk=user_id,
                is_active=True,
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
            User.DoesNotExist,
        ):
            # Если uid повреждён или пользователь
            # с таким ID не существует,
            # ссылка считается недействительной.
            return Response(
                {
                    "detail": "Invalid password reset link."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем токен, созданный Django.
        #
        # Здесь Django проверяет, что токен:
        # - принадлежит этому пользователю;
        # - не просрочен;
        # - не был сделан недействительным
        #   изменением состояния пользователя.
        if not default_token_generator.check_token(
            user,
            token,
        ):
            return Response(
                {
                    "detail": "Invalid password reset link."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Теперь пользователь известен и token подтверждён.
        #
        # Передаём user в context serializer.
        # Это необходимо для UserAttributeSimilarityValidator,
        # который может проверить новый пароль
        # на сходство с данными пользователя.
        serializer = self.get_serializer(
            data=request.data,
            context={
                "request": request,
                "user": user,
            },
        )

        # Проверяем новый пароль всеми стандартными
        # Django password validators.
        serializer.is_valid(raise_exception=True)

        # Получаем уже проверенный новый пароль.
        new_password = serializer.validated_data["new_password"]

        # set_password() правильно хеширует пароль
        # перед сохранением в базе данных.
        user.set_password(new_password)

        # Сохраняем изменённый пароль.
        user.save()

        return Response(
            {
                "detail": "Password has been reset successfully."
            },
            status=status.HTTP_200_OK,
        )

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
class HouseholdMemberDetailView(generics.GenericAPIView):
    serializer_class = UpdateHouseholdMemberSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch", "delete"]

    def get_queryset(self):
        # Ограничиваем QuerySet участниками Household,
        # указанного в URL.
        #
        # Благодаря этому нельзя изменить или удалить участника
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

        # Только OWNER может изменять или удалять участников.
        if not is_owner:
            raise PermissionDenied(
                "Only the household owner can manage members."
            )

        # Получаем участника только из текущего Household.
        #
        # Если member_id принадлежит другому Household,
        # объект не будет найден и вернётся 404.
        return get_object_or_404(
            self.get_queryset(),
            pk=self.kwargs["member_id"],
        )

    def patch(self, request, *args, **kwargs):
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
        serializer.save()

        # Возвращаем обновлённые данные участника.
        response_serializer = HouseholdMemberSerializer(
            instance,
            context=self.get_serializer_context(),
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):
        # Получаем участника с проверкой прав OWNER.
        instance = self.get_object()

        # OWNER не может удалить самого себя.
        if instance.user_id == request.user.id:
            raise PermissionDenied(
                "The household owner cannot remove themselves."
            )

        # OWNER не может удалить другого OWNER.
        if instance.role == HouseholdMembership.Role.OWNER:
            raise PermissionDenied(
                "The household owner cannot remove another owner."
            )

        # Удаляем membership.
        instance.delete()

        # DELETE успешно выполнен.
        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )
