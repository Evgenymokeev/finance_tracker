"""
Модели системы уведомлений.

Notification хранит само событие и его контекст.
NotificationDelivery отдельно отслеживает попытки доставки
уведомления через внешние каналы.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    """
    Уведомление конкретного пользователя.

    event_key обеспечивает идемпотентность: повторная обработка
    одного события не должна создавать дубликаты для пользователя.

    data хранит снимок контекста события, чтобы уведомление
    сохраняло смысл даже после изменения или удаления исходной
    финансовой сущности.
    """

    class NotificationType(models.TextChoices):
        BUDGET_EXCEEDED = (
            "budget_exceeded",
            "Budget exceeded",
        )
        BUDGET_WARNING = (
            "budget_warning",
            "Budget warning",
        )
        EXPENSE_CREATED = (
            "expense_created",
            "Expense created",
        )
        GOAL_COMPLETED = (
            "goal_completed",
            "Goal completed",
        )
        GOAL_CONTRIBUTION = (
            "goal_contribution",
            "Goal contribution",
        )
        GOAL_WITHDRAWAL = (
            "goal_withdrawal",
            "Goal withdrawal",
        )
        DAILY_SUMMARY = (
            "daily_summary",
            "Daily summary",
        )
        HOUSEHOLD_BUDGET_EXCEEDED = (
            "household_budget_exceeded",
            "Household budget exceeded",
        )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
    )

    title = models.CharField(max_length=255)
    message = models.TextField()

    # NULL разрешён для старых уведомлений, созданных до
    # внедрения NotificationService. Новые уведомления
    # сервис будет создавать с обязательным event_key.
    event_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    # Снимок данных события: сумма, валюта, категория,
    # период и другие сведения, необходимые для истории.
    data = models.JSONField(default=dict, blank=True)

    # Язык пользователя на момент создания уведомления.
    # Не зависит от последующего изменения его настроек.
    locale = models.CharField(
        max_length=10,
        default="en",
    )

    is_read = models.BooleanField(default=False)

    # Бюджет может быть удалён, но само уведомление
    # и сохранённый контекст события должны остаться.
    budget = models.ForeignKey(
        "budgets.Budget",
        on_delete=models.SET_NULL,
        related_name="notifications",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Один пользователь не должен получить одно
            # и то же бизнес-событие более одного раза.
            # Разные event_key могут относиться к одному бюджету.
            # NULL оставлен для исторических записей.
            models.UniqueConstraint(
                fields=["user", "event_key"],
                condition=Q(event_key__isnull=False),
                name="unique_user_notification_event",
            ),
        ]

    def __str__(self):
        return f"User {self.user_id} - {self.notification_type}"


class NotificationDelivery(models.Model):
    """
    Отслеживает доставку уведомления через отдельный канал.

    Одна запись соответствует одному каналу для одного
    уведомления. Повторные попытки доставки учитываются
    счётчиком attempts_count, а не созданием новых записей.
    """

    class Channel(models.TextChoices):
        EMAIL = ("email", "Email")
        PUSH = ("push", "Push")
        TELEGRAM = ("telegram", "Telegram")

    class Status(models.TextChoices):
        PENDING = ("pending", "Pending")
        PROCESSING = ("processing", "Processing")
        SENT = ("sent", "Sent")
        FAILED = ("failed", "Failed")

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )

    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
    )

    # Снимок адреса получателя на момент создания доставки.
    # Для EMAIL здесь хранится email пользователя.
    # Это защищает уже созданную доставку от изменения
    # адреса в профиле до фактической отправки.
    recipient = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    attempts_count = models.PositiveIntegerField(default=0)

    next_attempt_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Время, до которого доставка зарезервирована dispatcher
    # и не должна повторно отправляться в Celery.
    # Если публикация задачи или запуск worker не состоялись,
    # резервирование автоматически истечёт.
    dispatch_locked_until = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Время, до которого доставка закреплена за текущим worker.
    # После истечения lease другой worker сможет восстановить обработку.
    locked_until = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Уникальный токен конкретного захвата доставки.
    # Не позволяет устаревшему worker перезаписать результат
    # более новой попытки обработки.
    claim_token = models.UUIDField(
        null=True,
        blank=True,
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Для одного уведомления создаётся не более
            # одной записи доставки на каждый канал.
            models.UniqueConstraint(
                fields=["notification", "channel"],
                name="unique_notification_delivery_channel",
            ),
        ]

    def __str__(self):
        return (
            f"Notification {self.notification_id} - "
            f"{self.channel} - {self.status}"
        )
