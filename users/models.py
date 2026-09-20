from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Profile: {self.user.username}"


class UserSettings(models.Model):

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        RUSSIAN = "ru", "Russian"
        CZECH = "cs", "Czech"

    class Currency(models.TextChoices):
        CZK = "CZK", "Czech koruna"
        EUR = "EUR", "Euro"
        USD = "USD", "US dollar"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="settings",
    )

    language = models.CharField(
        max_length=2,
        choices=Language.choices,
        default=Language.ENGLISH,
    )

    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.CZK,
    )

    timezone = models.CharField(
        max_length=64,
        default="UTC",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Settings: {self.user.username}"


class NotificationSettings(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_settings",
    )

    email_enabled = models.BooleanField(
        default=True,
    )

    push_enabled = models.BooleanField(
        default=True,
    )

    telegram_enabled = models.BooleanField(
        default=False,
    )

    daily_summary = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Notification settings: {self.user.username}"


class Household(models.Model):

    name = models.CharField(
        max_length=255,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_households",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name


class HouseholdMembership(models.Model):

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADULT = "adult", "Adult"
        CHILD = "child", "Child"

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="household_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )

    joined_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["household", "user"],
                name="unique_household_user_membership",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.household.name} - "
            f"{self.role}"
        )
