from django.contrib.auth.models import User
from django.db import models


class Expense(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    title = models.CharField(
        max_length=100,
        verbose_name="Название"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма"
    )

    category = models.CharField(
        max_length=50,
        verbose_name="Категория"
    )

    date = models.DateField(
        verbose_name="Дата"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )