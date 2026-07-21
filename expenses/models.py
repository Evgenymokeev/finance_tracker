from django.db import models


class Expense(models.Model):
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

    class Meta:
        ordering = ["-date"]
        verbose_name = "Расход"
        verbose_name_plural = "Расходы"

    def __str__(self):
        return f"{self.title} - {self.amount}"

# Create your models here.
