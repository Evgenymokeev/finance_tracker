from django.contrib.auth.models import User
from django.db import models


class FinancialGoal(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="financial_goals",
    )

    title = models.CharField(
        max_length=255,
    )

    target_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    current_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    deadline = models.DateField(
        null=True,
        blank=True,
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
