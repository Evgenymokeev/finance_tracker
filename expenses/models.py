from django.contrib.auth.models import User
from django.db import models

from categories.models import Category


class Expense(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )

    title = models.CharField(
        max_length=100,
        verbose_name="Название",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="Категория",
    )

    goal = models.ForeignKey(
        "goals.FinancialGoal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
        verbose_name="Финансовая цель",
    )

    date = models.DateField(
        verbose_name="Дата",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Описание",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Расход"
        verbose_name_plural = "Расходы"

    def __str__(self):
        return f"{self.title} - {self.amount}"