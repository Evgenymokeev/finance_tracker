"""
Модели бюджетов пользователя.

Бюджет хранит лимит расходов для определённой категории
за конкретный месяц. Валюта бюджета определяет, в какой
валюте задан лимит и в которой нужно рассчитывать расходы
перед сравнением с этим лимитом.
"""

from django.conf import settings
from django.db import models

from users.models import UserSettings


class Budget(models.Model):
    """
    Представляет месячный бюджет пользователя
    для определённой категории расходов.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="budgets",
    )

    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.CASCADE,
        related_name="budgets",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    # Валюта лимита бюджета.
    # Расходы необходимо приводить к этой валюте
    # перед сравнением с установленным лимитом.
    currency = models.CharField(
        max_length=3,
        choices=UserSettings.Currency.choices,
        default=UserSettings.Currency.CZK,
        verbose_name="Валюта бюджета",
    )

    # Первый день месяца, для которого задан бюджет.
    month = models.DateField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        """Настройки сортировки и ограничения бюджетов."""

        ordering = ["-month", "category__name"]

        constraints = [
            # У пользователя может быть только один бюджет
            # для категории в пределах одного месяца.
            models.UniqueConstraint(
                fields=["user", "category", "month"],
                name="unique_user_category_month_budget",
            ),
        ]

    def __str__(self):
        """Возвращает краткое представление бюджета."""

        return (
            f"{self.user.username} - "
            f"{self.category.name} - "
            f"{self.month:%Y-%m}"
        )
