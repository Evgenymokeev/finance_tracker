from django.core.validators import MinValueValidator
from django.db import models

from users.models import UserSettings


class ExchangeRate(models.Model):
    """
    Исторический курс одной валюты относительно другой.

    Например:

        CZK → EUR
        rate = 0.0395
        date = 2026-10-06

    Одна запись представляет курс конкретной пары валют
    на конкретную дату.
    """

    base_currency = models.CharField(
        max_length=3,
        choices=UserSettings.Currency.choices,
        verbose_name="Базовая валюта",
    )
    target_currency = models.CharField(
        max_length=3,
        choices=UserSettings.Currency.choices,
        verbose_name="Целевая валюта",
    )
    rate = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        validators=[
            MinValueValidator(0.0000000001),
        ],
        verbose_name="Курс",
    )
    date = models.DateField(
        verbose_name="Дата курса",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )

    class Meta:
        """
        Дополнительные настройки и ограничения модели.
        """

        ordering = [
            "-date",
            "base_currency",
            "target_currency",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "base_currency",
                    "target_currency",
                    "date",
                ],
                name="unique_exchange_rate_per_day",
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    base_currency=models.F("target_currency"),
                ),
                name="different_exchange_rate_currencies",
            ),
            models.CheckConstraint(
                condition=models.Q(rate__gt=0),
                name="positive_exchange_rate",
            ),
        ]

        verbose_name = "Курс валюты"
        verbose_name_plural = "Курсы валют"

    def __str__(self):
        """
        Человекочитаемое представление курса.

        Например:

            CZK → EUR: 0.0395000000 (2026-10-06)
        """

        return (
            f"{self.base_currency} → "
            f"{self.target_currency}: "
            f"{self.rate} "
            f"({self.date})"
        )
