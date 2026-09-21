from django.contrib.auth.models import User
from rest_framework import serializers
from django.db import transaction
from .models import (
    Household,
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