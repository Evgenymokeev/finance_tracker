"""
Модели финансовых целей и накоплений.

FinancialGoal хранит целевую и текущую суммы в валюте цели.
Автоматические накопления и транзакции используют ту же валюту,
чтобы денежные значения одной цели оставались согласованными.
"""

from django.contrib.auth.models import User
from django.db import models

from users.models import UserSettings


class FinancialGoal(models.Model):
    """
    Представляет финансовую цель пользователя.

    Целевая сумма, текущие накопления и связанные операции
    должны использовать валюту, указанную в поле currency.
    """

    class Status(models.TextChoices):
        """Допустимые состояния финансовой цели."""

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

    # Валюта целевой суммы и текущих накоплений.
    # Пополнения и снятия должны выполняться в этой валюте.
    currency = models.CharField(
        max_length=3,
        choices=UserSettings.Currency.choices,
        default=UserSettings.Currency.CZK,
        verbose_name="Валюта финансовой цели",
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
        """Настройки сортировки финансовых целей."""

        ordering = ["-created_at"]

    def __str__(self):
        """Возвращает название финансовой цели."""

        return self.title


class GoalAutomaticSaving(models.Model):
    """
    Настройки автоматического пополнения финансовой цели.

    Сумма автоматического пополнения выражается в валюте
    связанной финансовой цели.
    """

    class Frequency(models.TextChoices):
        """Поддерживаемые интервалы автоматических накоплений."""

        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"
        CUSTOM = "custom", "Custom"

    goal = models.OneToOneField(
        FinancialGoal,
        on_delete=models.CASCADE,
        related_name="automatic_saving",
    )

    # Сумма одного автоматического пополнения
    # в валюте связанной финансовой цели.
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
    )

    # Интервал применяется для периодичности CUSTOM.
    interval = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    next_run_at = models.DateTimeField()

    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        """Настройки сортировки автоматических накоплений."""

        ordering = ["next_run_at"]

    def __str__(self):
        """Возвращает текстовое представление настройки накоплений."""

        return f"Automatic saving for {self.goal.title}"


class GoalSavingTransaction(models.Model):
    """
    Представляет пополнение или снятие средств с финансовой цели.

    Сумма транзакции выражается в валюте связанной цели.
    Отдельная валюта транзакции не задаётся.
    """

    class TransactionType(models.TextChoices):
        """Допустимые типы операций с накоплениями."""

        DEPOSIT = "deposit", "Deposit"
        WITHDRAWAL = "withdrawal", "Withdrawal"

    class Source(models.TextChoices):
        """Источники создания транзакции."""

        MANUAL = "manual", "Manual"
        AUTOMATIC = "automatic", "Automatic"

    goal = models.ForeignKey(
        FinancialGoal,
        on_delete=models.CASCADE,
        related_name="saving_transactions",
    )

    # Заполняется для транзакций, созданных
    # автоматическим накоплением.
    automatic_saving = models.ForeignKey(
        GoalAutomaticSaving,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    # Сумма операции в валюте финансовой цели.
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        default=TransactionType.DEPOSIT,
    )

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        """Настройки сортировки операций с накоплениями."""

        ordering = ["-created_at"]

    def __str__(self):
        """Возвращает текстовое представление транзакции."""

        return f"{self.goal.title}: {self.amount}"
