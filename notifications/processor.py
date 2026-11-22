"""
Процессор доставки уведомлений.

DeliveryProcessor управляет жизненным циклом NotificationDelivery:
захватом записи worker, отправкой через provider и сохранением
результата обработки.

Внешние вызовы выполняются вне транзакций PostgreSQL.
"""

import uuid
import random
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import NotificationDelivery
from .providers.base import (
    PermanentDeliveryError,
    TemporaryDeliveryError,
)
from .providers.email import EmailSender


class DeliveryProcessor:
    """
    Управляет полным жизненным циклом NotificationDelivery.

    Отвечает за:
    - атомарный захват доставки отдельным worker;
    - защиту от параллельной обработки через claim_token и lease;
    - восстановление зависших доставок;
    - контроль максимального количества попыток;
    - расчёт exponential backoff и jitter;
    - планирование повторных попыток после временных ошибок;
    - фиксацию успешной и окончательной неудачной доставки.

    Внешние вызовы провайдеров выполняются вне транзакций БД.
    Результат обработки может сохранить только worker с актуальным
    claim_token, что защищает состояние доставки от устаревших worker.
    """
    @staticmethod
    def fail_exhausted_deliveries():
        """
        Завершает доставки, исчерпавшие допустимое число попыток.

        PENDING-доставка с достигнутым лимитом больше не должна
        ожидать следующего запуска.

        PROCESSING-доставка переводится в FAILED только после
        истечения lease: активный worker должен иметь возможность
        завершить свою попытку.

        Блокировка строк защищает от одновременного изменения
        одной доставки несколькими worker.
        """
        now = timezone.now()
        max_attempts = settings.NOTIFICATION_MAX_ATTEMPTS

        exhausted = (
            Q(
                status=NotificationDelivery.Status.PENDING,
                attempts_count__gte=max_attempts,
            )
            | Q(
                status=NotificationDelivery.Status.PROCESSING,
                attempts_count__gte=max_attempts,
            ) & (
                Q(locked_until__lte=now)
                | Q(locked_until__isnull=True)
            )
        )

        with transaction.atomic():
            deliveries = list(
                NotificationDelivery.objects
                .select_for_update(skip_locked=True)
                .filter(exhausted)
            )

            if not deliveries:
                return 0

            delivery_ids = [delivery.pk for delivery in deliveries]

            return NotificationDelivery.objects.filter(
                pk__in=delivery_ids,
            ).update(
                status=NotificationDelivery.Status.FAILED,
                claim_token=None,
                locked_until=None,
                dispatch_locked_until=None,
                next_attempt_at=None,
                last_error="Maximum delivery attempts exceeded.",
                updated_at=now,
            )

    @staticmethod
    def calculate_retry_delay(attempt):
        """
        Рассчитывает задержку перед следующей попыткой доставки.

        Использует exponential backoff с ограничением максимальной
        задержки и случайным jitter, чтобы распределить повторные
        запросы к внешнему почтовому серверу во времени.

        attempt — номер уже выполненной попытки.
        """
        base_delay = settings.NOTIFICATION_RETRY_BASE_DELAY
        max_delay = settings.NOTIFICATION_RETRY_MAX_DELAY
        jitter = settings.NOTIFICATION_RETRY_JITTER

        exponential_delay = base_delay * (2 ** (attempt - 1))
        capped_delay = min(exponential_delay, max_delay)

        jitter_factor = random.uniform(
            1 - jitter,
            1 + jitter,
        )

        return min(
            max_delay,
            max(0, capped_delay * jitter_factor),
        )

    @staticmethod
    def schedule_retry(delivery_id, claim_token, error):
        """
        Планирует повторную попытку после временной ошибки.

        Обновление разрешено только worker с актуальным claim_token.
        Если лимит попыток исчерпан, доставка окончательно
        переводится в FAILED.

        Возвращает:
            True, если состояние доставки обновлено.
            False, если worker потерял владение доставкой.
        """
        now = timezone.now()
        max_attempts = settings.NOTIFICATION_MAX_ATTEMPTS

        with transaction.atomic():
            delivery = (
                NotificationDelivery.objects
                .select_for_update()
                .filter(
                    pk=delivery_id,
                    status=NotificationDelivery.Status.PROCESSING,
                    claim_token=claim_token,
                )
                .first()
            )

            if delivery is None:
                return False

            error_message = str(error)[:4000]

            if delivery.attempts_count >= max_attempts:
                delivery.status = NotificationDelivery.Status.FAILED
                delivery.next_attempt_at = None
            else:
                delay = DeliveryProcessor.calculate_retry_delay(
                    delivery.attempts_count,
                )
                delivery.status = NotificationDelivery.Status.PENDING
                delivery.next_attempt_at = now + timedelta(
                    seconds=delay,
                )

            delivery.last_error = error_message
            delivery.claim_token = None
            delivery.locked_until = None
            delivery.dispatch_locked_until = None

            delivery.save(
                update_fields=[
                    "status",
                    "next_attempt_at",
                    "last_error",
                    "claim_token",
                    "locked_until",
                    "dispatch_locked_until",
                    "updated_at",
                ],
            )

            return True

    @staticmethod
    def mark_failed(delivery_id, claim_token, error):
        """
        Окончательно завершает доставку после постоянной ошибки.

        Изменение разрешено только worker с актуальным claim_token.
        Повторная попытка для такой ошибки не планируется.

        Возвращает:
            True, если состояние доставки обновлено.
            False, если worker потерял владение доставкой.
        """
        now = timezone.now()

        updated = NotificationDelivery.objects.filter(
            pk=delivery_id,
            status=NotificationDelivery.Status.PROCESSING,
            claim_token=claim_token,
        ).update(
            status=NotificationDelivery.Status.FAILED,
            next_attempt_at=None,
            locked_until=None,
            dispatch_locked_until=None,
            claim_token=None,
            last_error=str(error)[:4000],
            updated_at=now,
        )

        return updated == 1

    @staticmethod
    def mark_sent(delivery_id, claim_token):
        """
        Отмечает доставку успешно отправленной.

        Результат может сохранить только worker, который всё ещё
        владеет актуальным claim_token.

        Условное обновление выполняется одним SQL-запросом:
        устаревший worker не сможет изменить доставку после того,
        как другой worker повторно захватил её.

        Возвращает:
            True, если доставка успешно обновлена.
            False, если token устарел или доставка уже не PROCESSING.
        """
        now = timezone.now()

        updated = NotificationDelivery.objects.filter(
            pk=delivery_id,
            status=NotificationDelivery.Status.PROCESSING,
            claim_token=claim_token,
        ).update(
            status=NotificationDelivery.Status.SENT,
            sent_at=now,
            next_attempt_at=None,
            locked_until=None,
            dispatch_locked_until=None,
            claim_token=None,
            last_error="",
            updated_at=now,
        )

        return updated == 1

    @staticmethod
    def claim_delivery(delivery_id=None):
        """
        Атомарно захватывает одну готовую доставку.

        Если delivery_id указан, пытается захватить конкретную
        запись. Иначе выбирает первую доступную доставку.

        Доступны:
        - PENDING с next_attempt_at=NULL;
        - PENDING с наступившим next_attempt_at;
        - PROCESSING с истёкшим locked_until.

        select_for_update(skip_locked=True) позволяет нескольким
        worker одновременно выбирать разные записи.

        При каждом захвате:
        - статус устанавливается в PROCESSING;
        - attempts_count увеличивается;
        - создаётся новый claim_token;
        - устанавливается срок lease.

        Возвращает:
            NotificationDelivery или None.
        """
        now = timezone.now()

        # Сначала завершаем доставки, исчерпавшие лимит попыток.
        DeliveryProcessor.fail_exhausted_deliveries()

        lease_seconds = settings.NOTIFICATION_DELIVERY_LEASE

        with transaction.atomic():
            queryset = NotificationDelivery.objects.select_for_update(
                skip_locked=True,
            )

            if delivery_id is not None:
                queryset = queryset.filter(pk=delivery_id)

            eligible = (
                Q(
                    status=NotificationDelivery.Status.PENDING,
                )
                & (
                    Q(next_attempt_at__isnull=True)
                    | Q(next_attempt_at__lte=now)
                )
            ) | (
                Q(
                    status=NotificationDelivery.Status.PROCESSING,
                )
                & (
                    Q(locked_until__lte=now)
                    | Q(locked_until__isnull=True)
                )
            )

            delivery = (
                queryset
                .filter(eligible)
                .order_by("created_at", "pk")
                .first()
            )

            if delivery is None:
                return None

            delivery.status = NotificationDelivery.Status.PROCESSING
            delivery.attempts_count += 1
            delivery.claim_token = uuid.uuid4()
            delivery.locked_until = now + timedelta(
                seconds=lease_seconds,
            )
            delivery.next_attempt_at = None
            delivery.dispatch_locked_until = None

            delivery.save(
                update_fields=[
                    "status",
                    "attempts_count",
                    "claim_token",
                    "locked_until",
                    "next_attempt_at",
                    "dispatch_locked_until",
                    "updated_at",
                ],
            )

            return delivery

    @staticmethod
    def process_delivery(delivery_id=None):
        """
        Выполняет полный цикл обработки одной доставки.

        Сначала атомарно захватывает запись, затем отправляет
        уведомление через соответствующий provider вне транзакции.

        Временные ошибки планируют повторную попытку.
        Постоянные ошибки окончательно завершают доставку.

        Неожиданные исключения не перехватываются: доставка
        остаётся PROCESSING до истечения lease и может быть
        восстановлена другим worker.

        Возвращает:
            dict с результатом обработки или None, если
            доступной доставки нет.
        """
        delivery = DeliveryProcessor.claim_delivery(
            delivery_id=delivery_id,
        )

        if delivery is None:
            return None

        claim_token = delivery.claim_token

        try:
            if delivery.channel == NotificationDelivery.Channel.EMAIL:
                sender = EmailSender()
            else:
                raise PermanentDeliveryError(
                    f"Unsupported delivery channel: {delivery.channel}"
                )

            sender.send(delivery)

        except TemporaryDeliveryError as exc:
            updated = DeliveryProcessor.schedule_retry(
                delivery.id,
                claim_token,
                exc,
            )

            if updated:
                delivery.refresh_from_db(fields=["status"])
                result_status = delivery.status
            else:
                result_status = "ownership_lost"

            return {
                "delivery_id": delivery.id,
                "status": result_status,
            }

        except PermanentDeliveryError as exc:
            updated = DeliveryProcessor.mark_failed(
                delivery.id,
                claim_token,
                exc,
            )

            return {
                "delivery_id": delivery.id,
                "status": (
                    NotificationDelivery.Status.FAILED
                    if updated
                    else "ownership_lost"
                ),
            }

        updated = DeliveryProcessor.mark_sent(
            delivery.id,
            claim_token,
        )

        return {
            "delivery_id": delivery.id,
            "status": (
                NotificationDelivery.Status.SENT
                if updated
                else "ownership_lost"
            ),
        }
