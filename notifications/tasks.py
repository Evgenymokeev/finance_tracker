"""
Celery tasks для асинхронной доставки уведомлений.

PostgreSQL остаётся источником истины для состояния доставок.
Dispatcher периодически выбирает готовые записи, резервирует их
в БД и публикует задачи в Celery уже после завершения транзакции.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import NotificationDelivery
from .processor import DeliveryProcessor

logger = logging.getLogger(__name__)

# Ограничиваем количество задач, публикуемых за один цикл,
# чтобы не создавать чрезмерную нагрузку на брокер.
DISPATCH_BATCH_SIZE = 100

# Временное резервирование записи dispatcher.
# Если worker не получит задачу, резерв истечёт и запись
# снова станет доступна для публикации.
DISPATCH_RESERVATION_SECONDS = 120


@shared_task(
    name="notifications.tasks.process_notification_delivery",
)
def process_notification_delivery(delivery_id: int) -> dict | None:
    """
    Обрабатывает конкретную доставку уведомления.

    Передаёт управление DeliveryProcessor, который отвечает
    за атомарный захват записи, отправку через provider,
    контроль lease и сохранение результата.

    Args:
        delivery_id: ID записи NotificationDelivery.

    Returns:
        Результат обработки или None, если доставка
        уже недоступна для захвата.
    """
    return DeliveryProcessor.process_delivery(
        delivery_id=delivery_id,
    )


@shared_task(
    name="notifications.tasks.dispatch_pending_deliveries",
)
def dispatch_pending_deliveries() -> dict:
    """
    Находит готовые доставки и публикует задачи в Celery.

    Сначала записи резервируются в PostgreSQL внутри транзакции.
    Публикация задач выполняется только после её завершения.

    Это предотвращает повторную публикацию одной доставки
    каждым периодическим запуском dispatcher.

    Если публикация отдельной задачи завершается ошибкой,
    резервирование этой записи освобождается. Остальные
    доставки продолжают обрабатываться независимо.

    Returns:
        Количество выбранных, опубликованных и не опубликованных
        доставок.
    """
    now = timezone.now()

    # Сначала завершаем записи, исчерпавшие лимит попыток.
    # Они не должны повторно попадать в очередь Celery.
    DeliveryProcessor.fail_exhausted_deliveries()

    reservation_deadline = now + timedelta(
        seconds=DISPATCH_RESERVATION_SECONDS,
    )

    # Разрешаем выбирать:
    # 1. PENDING с наступившим временем следующей попытки.
    # 2. PROCESSING с истёкшим worker lease.
    eligible = (
        Q(
            status=NotificationDelivery.Status.PENDING,
            attempts_count__lt=settings.NOTIFICATION_MAX_ATTEMPTS,
        )
        & (
            Q(next_attempt_at__isnull=True)
            | Q(next_attempt_at__lte=now)
        )
    ) | (
        Q(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count__lt=settings.NOTIFICATION_MAX_ATTEMPTS,
        )
        & (
            Q(locked_until__lte=now)
            | Q(locked_until__isnull=True)
        )
    )

    # Не выбираем записи, уже зарезервированные другим
    # циклом dispatcher.
    reservation_available = (
        Q(dispatch_locked_until__isnull=True)
        | Q(dispatch_locked_until__lte=now)
    )

    with transaction.atomic():
        deliveries = list(
            NotificationDelivery.objects
            .select_for_update(skip_locked=True)
            .filter(eligible & reservation_available)
            .order_by("created_at", "pk")[:DISPATCH_BATCH_SIZE]
        )

        delivery_ids = []

        for delivery in deliveries:
            delivery.dispatch_locked_until = reservation_deadline
            delivery.save(
                update_fields=[
                    "dispatch_locked_until",
                    "updated_at",
                ],
            )
            delivery_ids.append(delivery.pk)

    # Важно: этот цикл выполняется уже вне транзакции.
    dispatched = 0
    failed = 0

    for delivery_id in delivery_ids:
        try:
            process_notification_delivery.delay(delivery_id)
        except Exception:
            failed += 1

            logger.exception(
                "Failed to enqueue notification delivery %s.",
                delivery_id,
            )

            # Освобождаем только наше резервирование.
            # Если запись уже захвачена worker или получила
            # новое резервирование, чужое состояние не затрагиваем.
            NotificationDelivery.objects.filter(
                pk=delivery_id,
                dispatch_locked_until=reservation_deadline,
            ).update(
                dispatch_locked_until=None,
                updated_at=timezone.now(),
            )
        else:
            dispatched += 1

    return {
        "selected": len(delivery_ids),
        "dispatched": dispatched,
        "failed": failed,
    }
