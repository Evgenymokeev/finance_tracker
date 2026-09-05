from django.contrib.auth.models import User
from django.db import models


class Notification(models.Model):

    class NotificationType(models.TextChoices):
        BUDGET_EXCEEDED = (
            "budget_exceeded",
            "Budget exceeded",
        )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
    )

    title = models.CharField(
        max_length=255,
    )

    message = models.TextField()

    is_read = models.BooleanField(
        default=False,
    )

    budget = models.ForeignKey(
        "budgets.Budget",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "budget",
                    "notification_type",
                ],
                name="unique_budget_notification",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.notification_type}"
        )