from django.contrib.auth.models import User
from rest_framework import serializers
from django.db import transaction
from .models import (
    Household,
    HouseholdMembership,
    NotificationSettings,
    UserProfile,
    UserSettings,
)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    email = serializers.EmailField(
        required=True,
    )

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )

        return value
    
    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)

        UserProfile.objects.create(
            user=user,
        )

        UserSettings.objects.create(
            user=user,
        )

        NotificationSettings.objects.create(
            user=user,
        )

        return user

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
        )
        read_only_fields = (
            "username",
        )

    def validate_email(self, value):
        user = self.instance

        if (
            User.objects
            .filter(email__iexact=value)
            .exclude(pk=user.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "A user with this email already exists."
            )

        return value

class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = (
            "language",
            "currency",
            "timezone",
        )


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = (
            "email_enabled",
            "push_enabled",
            "telegram_enabled",
            "daily_summary",
        )


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True,
    )

    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
    )


class HouseholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Household
        fields = (
            "id",
            "name",
            "created_by",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "created_by",
            "created_at",
            "updated_at",
        )

class HouseholdMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )

    class Meta:
        model = HouseholdMembership
        fields = (
            "id",
            "user",
            "username",
            "role",
        )

        read_only_fields = (
            "id",
            "user",
            "username",
            "role",
        )

class HouseholdMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )

    class Meta:
        model = HouseholdMembership
        fields = (
            "id",
            "user",
            "username",
            "role",
        )

        read_only_fields = (
            "id",
            "user",
            "username",
            "role",
        )

class AddHouseholdMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = HouseholdMembership
        fields = (
            "user",
            "role",
        )

    def validate_role(self, value):
        # Пользователь не может добавить нового OWNER
        # через обычное добавление участника.
        #
        # В Household должен оставаться только один OWNER,
        # который автоматически создаётся при создании Household.
        if value == HouseholdMembership.Role.OWNER:
            raise serializers.ValidationError(
                "A new household member cannot have the owner role."
            )

        return value

    def validate(self, attrs):
        household = self.context["household"]
        user = attrs["user"]

        # Проверяем, не является ли пользователь уже
        # участником этого Household.
        #
        # Благодаря этому мы заранее возвращаем понятную
        # ошибку вместо ошибки уникального ограничения базы данных.
        if HouseholdMembership.objects.filter(
            household=household,
            user=user,
        ).exists():
            raise serializers.ValidationError(
                {
                    "user": (
                        "This user is already a member "
                        "of this household."
                    )
                }
            )

        return attrs


class UpdateHouseholdMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = HouseholdMembership
        fields = (
            "role",
        )

    def validate(self, attrs):
        # Получаем исходные данные запроса.
        request_data = self.initial_data

        # Разрешаем изменять только поле role.
        allowed_fields = {"role"}

        # Находим поля, которые клиент попытался передать,
        # но которые не разрешены для изменения.
        unexpected_fields = set(request_data.keys()) - allowed_fields

        if unexpected_fields:
            raise serializers.ValidationError(
                {
                    field: "This field cannot be changed."
                    for field in unexpected_fields
                }
            )

        # Получаем текущий membership.
        membership = self.instance

        # Получаем пользователя, который выполняет запрос.
        request = self.context["request"]

        # Нельзя изменять собственную роль владельца.
        #
        # Иначе OWNER сможет убрать у себя
        # права владельца, что нарушит правила Household.
        if (
            membership.user == request.user
            and membership.role == HouseholdMembership.Role.OWNER
        ):
            raise serializers.ValidationError(
                {
                    "role": (
                        "The household owner cannot change "
                        "their own role."
                    )
                }
            )

        return attrs

    def validate_role(self, value):
        # Нельзя назначить участнику роль OWNER.
        #
        # В нашем приложении OWNER создаётся автоматически
        # при создании Household.
        #
        # Через PATCH разрешаем менять только роли
        # ADULT и CHILD.
        if value == HouseholdMembership.Role.OWNER:
            raise serializers.ValidationError(
                "A household member cannot be assigned the owner role."
            )

        return value