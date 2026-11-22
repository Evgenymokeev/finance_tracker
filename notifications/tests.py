import smtplib
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from .processor import DeliveryProcessor

from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import (
    TestCase,
    TransactionTestCase,
    override_settings,
)
from rest_framework import status
from rest_framework.test import APITestCase

from budgets.models import Budget
from categories.models import Category
from users.models import NotificationSettings, UserSettings

from .delivery import DeliveryService
from .models import Notification, NotificationDelivery
from .orchestrators import NotificationOrchestrator
from .providers.base import (
    PermanentDeliveryError,
    TemporaryDeliveryError,
)
from .providers.email import EmailSender
from .services import NotificationService
from django.conf import settings
from .tasks import dispatch_pending_deliveries


@override_settings(
    EMAIL_HOST="smtp.example.com",
    DEFAULT_FROM_EMAIL="noreply@example.com",
)
class EmailSenderTest(TestCase):
    """
    Проверяет Email-провайдер без реальной отправки писем.

    Все обращения к Django send_mail заменяются mock-объектами.
    Тесты проверяют передачу содержимого уведомления,
    использование сохранённого адреса получателя
    и классификацию ошибок SMTP.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="email_test_user",
            email="original@example.com",
            password="testpass123",
        )

        self.notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="email:test:event",
            title="Test notification",
            message="Test notification message",
        )

        self.delivery = NotificationDelivery.objects.create(
            notification=self.notification,
            channel=NotificationDelivery.Channel.EMAIL,
            recipient="recipient@example.com",
        )

        self.sender = EmailSender()

    @patch("notifications.providers.email.send_mail")
    def test_successful_email_delivery(self, mock_send_mail):
        """
        Успешная отправка возвращает количество переданных писем.
        """
        mock_send_mail.return_value = 1

        result = self.sender.send(self.delivery)

        self.assertEqual(result, 1)

        mock_send_mail.assert_called_once_with(
            subject="Test notification",
            message="Test notification message",
            from_email="noreply@example.com",
            recipient_list=["recipient@example.com"],
            fail_silently=False,
        )

    @patch("notifications.providers.email.send_mail")
    def test_delivery_uses_saved_recipient(self, mock_send_mail):
        """
        Изменение email пользователя не меняет получателя доставки.
        """
        self.user.email = "new@example.com"
        self.user.save(update_fields=["email"])

        mock_send_mail.return_value = 1

        self.sender.send(self.delivery)

        self.assertEqual(
            mock_send_mail.call_args.kwargs["recipient_list"],
            ["recipient@example.com"],
        )

    def test_empty_recipient_is_permanent_error(self):
        """
        Без адреса получателя отправка невозможна.
        """
        self.delivery.recipient = ""

        with patch("notifications.providers.email.send_mail") as mock_send_mail:
            with self.assertRaises(PermanentDeliveryError):
                self.sender.send(self.delivery)

        mock_send_mail.assert_not_called()

    @override_settings(EMAIL_HOST="")
    def test_missing_smtp_host_is_permanent_error(self):
        """
        Отсутствие SMTP-конфигурации не должно запускать отправку.
        """
        with patch("notifications.providers.email.send_mail") as mock_send_mail:
            with self.assertRaises(PermanentDeliveryError):
                self.sender.send(self.delivery)

        mock_send_mail.assert_not_called()

    @patch("notifications.providers.email.send_mail")
    def test_temporary_smtp_error_is_retryable(self, mock_send_mail):
        """
        SMTP-код 421 классифицируется как временная ошибка.
        """
        mock_send_mail.side_effect = smtplib.SMTPResponseException(
            421,
            b"Service temporarily unavailable",
        )

        with self.assertRaises(TemporaryDeliveryError):
            self.sender.send(self.delivery)

    @patch("notifications.providers.email.send_mail")
    def test_authentication_error_535_is_permanent(
        self,
        mock_send_mail,
    ):
        """
        SMTP-код 535 означает постоянную ошибку аутентификации.
        """
        mock_send_mail.side_effect = smtplib.SMTPAuthenticationError(
            535,
            b"Authentication credentials invalid",
        )

        with self.assertRaises(PermanentDeliveryError):
            self.sender.send(self.delivery)

    @patch("notifications.providers.email.send_mail")
    def test_temporary_recipient_refusal_is_retryable(
        self,
        mock_send_mail,
    ):
        """
        SMTP-код 450 означает временный отказ получателя.
        """
        mock_send_mail.side_effect = smtplib.SMTPRecipientsRefused(
            {
                "recipient@example.com": (
                    450,
                    b"Mailbox temporarily unavailable",
                )
            }
        )

        with self.assertRaises(TemporaryDeliveryError):
            self.sender.send(self.delivery)

    @patch("notifications.providers.email.send_mail")
    def test_permanent_recipient_refusal_is_not_retryable(
        self,
        mock_send_mail,
    ):
        """
        SMTP-код 550 означает постоянный отказ получателя.
        """
        mock_send_mail.side_effect = smtplib.SMTPRecipientsRefused(
            {
                "recipient@example.com": (
                    550,
                    b"Mailbox unavailable",
                )
            }
        )

        with self.assertRaises(PermanentDeliveryError):
            self.sender.send(self.delivery)

    @patch("notifications.providers.email.send_mail")
    def test_network_error_is_retryable(self, mock_send_mail):
        """
        Сетевой сбой классифицируется как временная ошибка.
        """
        mock_send_mail.side_effect = OSError(
            "Connection temporarily unavailable"
        )

        with self.assertRaises(TemporaryDeliveryError):
            self.sender.send(self.delivery)

    @patch("notifications.providers.email.send_mail")
    def test_unexpected_error_is_not_silently_classified(
        self,
        mock_send_mail,
    ):
        """
        Неожиданная ошибка программного уровня передаётся выше.
        """
        mock_send_mail.side_effect = RuntimeError(
            "Unexpected programming error"
        )

        with self.assertRaises(RuntimeError):
            self.sender.send(self.delivery)


class DeliveryProcessorClaimTest(TestCase):
    """
    Проверяет атомарный захват NotificationDelivery.

    Тесты проверяют готовность доставки, lease,
    увеличение счётчика попыток и защиту от повторного захвата.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="processor_test_user",
            email="processor@example.com",
            password="testpass123",
        )

        self.notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="processor:test:event",
            title="Test notification",
            message="Test message",
        )

    def create_delivery(self, **kwargs):
        """
        Создаёт тестовую доставку.

        По умолчанию используется EMAIL, но канал можно переопределить
        для проверки неподдерживаемых или будущих каналов доставки.
        """
        notification = kwargs.pop("notification", self.notification)
        channel = kwargs.pop(
            "channel",
            NotificationDelivery.Channel.EMAIL,
        )

        return NotificationDelivery.objects.create(
            notification=notification,
            channel=channel,
            recipient="processor@example.com",
            **kwargs,
        )

    @patch("notifications.processor.EmailSender.send")
    def test_process_delivery_marks_successful_email_as_sent(
        self,
        mock_send,
    ):
        """Успешная отправка переводит доставку в SENT."""
        delivery = self.create_delivery()

        result = DeliveryProcessor.process_delivery(delivery.id)

        self.assertEqual(
            result["status"],
            NotificationDelivery.Status.SENT,
        )
        self.assertEqual(result["delivery_id"], delivery.id)

        mock_send.assert_called_once()

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.SENT,
        )
        self.assertEqual(delivery.attempts_count, 1)
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)
        self.assertIsNotNone(delivery.sent_at)

    @patch(
        "notifications.processor.EmailSender.send",
        side_effect=TemporaryDeliveryError("SMTP temporarily unavailable"),
    )
    def test_process_delivery_schedules_retry_after_temporary_error(
        self,
        mock_send,
    ):
        """Временная ошибка возвращает доставку в PENDING."""
        delivery = self.create_delivery()

        result = DeliveryProcessor.process_delivery(delivery.id)

        self.assertEqual(
            result["status"],
            NotificationDelivery.Status.PENDING,
        )

        mock_send.assert_called_once()

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PENDING,
        )
        self.assertEqual(delivery.attempts_count, 1)
        self.assertIsNotNone(delivery.next_attempt_at)
        self.assertEqual(
            delivery.last_error,
            "SMTP temporarily unavailable",
        )
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)

    @patch(
        "notifications.processor.EmailSender.send",
        side_effect=PermanentDeliveryError("Invalid recipient"),
    )
    def test_process_delivery_marks_permanent_error_as_failed(
        self,
        mock_send,
    ):
        """Постоянная ошибка окончательно завершает доставку."""
        delivery = self.create_delivery()

        result = DeliveryProcessor.process_delivery(delivery.id)

        self.assertEqual(
            result["status"],
            NotificationDelivery.Status.FAILED,
        )

        mock_send.assert_called_once()

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.FAILED,
        )
        self.assertEqual(delivery.last_error, "Invalid recipient")
        self.assertIsNone(delivery.next_attempt_at)
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)

    @patch("notifications.processor.EmailSender.send")
    def test_process_delivery_fails_unsupported_channel(
        self,
        mock_send,
    ):
        """Неподдерживаемый канал завершается постоянной ошибкой."""
        delivery = self.create_delivery(
            channel=NotificationDelivery.Channel.PUSH,
        )

        result = DeliveryProcessor.process_delivery(delivery.id)

        self.assertEqual(
            result["status"],
            NotificationDelivery.Status.FAILED,
        )

        mock_send.assert_not_called()

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.FAILED,
        )
        self.assertIn("Unsupported delivery channel", delivery.last_error)

    @patch(
        "notifications.processor.EmailSender.send",
        side_effect=RuntimeError("Unexpected provider error"),
    )
    def test_process_delivery_preserves_lease_after_unexpected_error(
        self,
        mock_send,
    ):
        """
        Неожиданная ошибка передаётся выше, а lease сохраняется
        для последующего восстановления доставки.
        """
        delivery = self.create_delivery()

        with self.assertRaisesRegex(
            RuntimeError,
            "Unexpected provider error",
        ):
            DeliveryProcessor.process_delivery(delivery.id)

        mock_send.assert_called_once()

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PROCESSING,
        )
        self.assertEqual(delivery.attempts_count, 1)
        self.assertIsNotNone(delivery.claim_token)
        self.assertIsNotNone(delivery.locked_until)

    @patch(
        "notifications.processor.EmailSender.send",
        side_effect=TemporaryDeliveryError(
            "SMTP temporarily unavailable",
        ),
    )
    def test_process_delivery_returns_failed_when_attempt_limit_reached(
        self,
        mock_send,
    ):
        """
        Последняя разрешённая попытка при временной ошибке
        должна завершить доставку со статусом FAILED.
        """
        delivery = self.create_delivery(
            attempts_count=settings.NOTIFICATION_MAX_ATTEMPTS - 1,
        )

        result = DeliveryProcessor.process_delivery(
            delivery_id=delivery.id,
        )

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.FAILED,
        )
        self.assertEqual(
            result["status"],
            NotificationDelivery.Status.FAILED,
        )
        self.assertIsNone(delivery.next_attempt_at)
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)

        mock_send.assert_called_once()

    def test_claim_pending_delivery(self):
        """
        Готовая PENDING-доставка захватывается worker.
        """
        delivery = self.create_delivery()

        claimed = DeliveryProcessor.claim_delivery(delivery.id)

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.pk, delivery.pk)
        self.assertEqual(
            claimed.status,
            NotificationDelivery.Status.PROCESSING,
        )
        self.assertEqual(claimed.attempts_count, 1)
        self.assertIsNotNone(claimed.claim_token)
        self.assertIsNotNone(claimed.locked_until)
        self.assertIsNone(claimed.next_attempt_at)

    def test_claim_increments_attempts_and_replaces_token(self):
        """
        Повторный захват истёкшей доставки создаёт новый token.
        """
        old_token = "11111111-1111-1111-1111-111111111111"

        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=1,
            claim_token=old_token,
            locked_until=timezone.now() - timedelta(seconds=1),
        )

        claimed = DeliveryProcessor.claim_delivery(delivery.id)

        self.assertEqual(claimed.attempts_count, 2)
        self.assertNotEqual(str(claimed.claim_token), old_token)
        self.assertGreater(claimed.locked_until, timezone.now())

    def test_claim_clears_dispatch_reservation(self):
        """
        Worker очищает dispatcher reservation при захвате доставки.

        После перехода в PROCESSING управление доставкой
        принадлежит worker, поэтому резервирование публикации
        больше не требуется.
        """
        delivery = self.create_delivery(
            dispatch_locked_until=timezone.now() + timedelta(minutes=2),
        )

        claimed = DeliveryProcessor.claim_delivery(delivery.id)

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.status, NotificationDelivery.Status.PROCESSING)
        self.assertIsNone(claimed.dispatch_locked_until)

        delivery.refresh_from_db()
        self.assertIsNone(delivery.dispatch_locked_until)
        self.assertIsNotNone(delivery.locked_until)
        self.assertIsNotNone(delivery.claim_token)

    def test_future_retry_is_not_claimed(self):
        """
        PENDING-доставка с будущим next_attempt_at недоступна.
        """
        delivery = self.create_delivery(
            next_attempt_at=timezone.now() + timedelta(minutes=5),
        )

        claimed = DeliveryProcessor.claim_delivery(delivery.id)

        self.assertIsNone(claimed)

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PENDING,
        )
        self.assertEqual(delivery.attempts_count, 0)

    def test_active_processing_delivery_is_not_claimed(self):
        """
        Доставка с действующим lease не может быть захвачена повторно.
        """
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=1,
            claim_token="11111111-1111-1111-1111-111111111111",
            locked_until=timezone.now() + timedelta(minutes=2),
        )

        claimed = DeliveryProcessor.claim_delivery(delivery.id)

        self.assertIsNone(claimed)

    def test_sent_delivery_is_not_claimed(self):
        """
        Успешно отправленная доставка не обрабатывается повторно.
        """
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.SENT,
            sent_at=timezone.now(),
        )

        claimed = DeliveryProcessor.claim_delivery(delivery.id)

        self.assertIsNone(claimed)

    def test_failed_delivery_is_not_claimed(self):
        """
        Окончательно завершённая доставка не захватывается.
        """
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.FAILED,
        )

        claimed = DeliveryProcessor.claim_delivery(delivery.id)

        self.assertIsNone(claimed)

    def test_claim_without_id_selects_oldest_ready_delivery(self):
        first = self.create_delivery()

        second_notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            title="Second notification",
            message="Second message",
            event_key="processor:test:event:second",
        )
        second = self.create_delivery(notification=second_notification)

        claimed = DeliveryProcessor.claim_delivery()

        self.assertEqual(claimed.pk, first.pk)
        self.assertNotEqual(claimed.pk, second.pk)

    def test_unknown_delivery_id_returns_none(self):
        """
        Несуществующая запись не вызывает исключение.
        """
        claimed = DeliveryProcessor.claim_delivery(999999)

        self.assertIsNone(claimed)

    @override_settings(NOTIFICATION_MAX_ATTEMPTS=5)
    def test_exhausted_pending_delivery_is_failed(self):
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PENDING,
            attempts_count=5,
        )

        result = DeliveryProcessor.fail_exhausted_deliveries()

        self.assertEqual(result, 1)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.FAILED,
        )
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)
        self.assertIsNone(delivery.next_attempt_at)
        self.assertEqual(
            delivery.last_error,
            "Maximum delivery attempts exceeded.",
        )

    @override_settings(NOTIFICATION_MAX_ATTEMPTS=5)
    def test_expired_processing_delivery_is_failed(self):
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=5,
            locked_until=timezone.now() - timedelta(seconds=1),
            claim_token="12345678-1234-5678-1234-567812345678",
        )

        result = DeliveryProcessor.fail_exhausted_deliveries()

        self.assertEqual(result, 1)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.FAILED,
        )
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)

    @override_settings(NOTIFICATION_MAX_ATTEMPTS=5)
    def test_active_processing_delivery_is_not_failed(self):
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=5,
            locked_until=timezone.now() + timedelta(minutes=1),
        )

        result = DeliveryProcessor.fail_exhausted_deliveries()

        self.assertEqual(result, 0)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PROCESSING,
        )

    @override_settings(NOTIFICATION_MAX_ATTEMPTS=5)
    def test_delivery_below_attempt_limit_is_not_failed(self):
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PENDING,
            attempts_count=4,
        )

        result = DeliveryProcessor.fail_exhausted_deliveries()

        self.assertEqual(result, 0)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PENDING,
        )

    @override_settings(NOTIFICATION_MAX_ATTEMPTS=5)
    def test_no_exhausted_deliveries_returns_zero(self):
        result = DeliveryProcessor.fail_exhausted_deliveries()

        self.assertEqual(result, 0)

    def test_mark_sent_with_valid_token(self):
        token = "12345678-1234-5678-1234-567812345678"

        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            claim_token=token,
            locked_until=timezone.now() + timedelta(minutes=1),
        )

        result = DeliveryProcessor.mark_sent(
            delivery.pk,
            token,
        )

        self.assertTrue(result)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.SENT,
        )
        self.assertIsNotNone(delivery.sent_at)
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)
        self.assertIsNone(delivery.next_attempt_at)
        self.assertEqual(delivery.last_error, "")

    def test_mark_sent_rejects_stale_token(self):
        old_token = "12345678-1234-5678-1234-567812345678"
        current_token = "87654321-4321-8765-4321-876543218765"

        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            claim_token=current_token,
            locked_until=timezone.now() + timedelta(minutes=1),
        )

        result = DeliveryProcessor.mark_sent(
            delivery.pk,
            old_token,
        )

        self.assertFalse(result)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PROCESSING,
        )
        self.assertEqual(str(delivery.claim_token), current_token)
        self.assertIsNone(delivery.sent_at)

    def test_mark_sent_rejects_non_processing_delivery(self):
        token = "12345678-1234-5678-1234-567812345678"

        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PENDING,
            claim_token=token,
        )

        result = DeliveryProcessor.mark_sent(
            delivery.pk,
            token,
        )

        self.assertFalse(result)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PENDING,
        )

    @override_settings(
        NOTIFICATION_RETRY_BASE_DELAY=60,
        NOTIFICATION_RETRY_MAX_DELAY=3600,
        NOTIFICATION_RETRY_JITTER=0.2,
    )
    @patch("notifications.processor.random.uniform", return_value=1.0)
    def test_calculate_retry_delay_uses_exponential_backoff(self, mock_uniform):
        self.assertEqual(
            DeliveryProcessor.calculate_retry_delay(1),
            60,
        )
        self.assertEqual(
            DeliveryProcessor.calculate_retry_delay(2),
            120,
        )
        self.assertEqual(
            DeliveryProcessor.calculate_retry_delay(3),
            240,
        )
        self.assertEqual(
            DeliveryProcessor.calculate_retry_delay(4),
            480,
        )

        self.assertEqual(mock_uniform.call_count, 4)

    @override_settings(
        NOTIFICATION_RETRY_BASE_DELAY=60,
        NOTIFICATION_RETRY_MAX_DELAY=300,
        NOTIFICATION_RETRY_JITTER=0.2,
    )
    @patch("notifications.processor.random.uniform", return_value=1.0)
    def test_calculate_retry_delay_respects_maximum(self, mock_uniform):
        result = DeliveryProcessor.calculate_retry_delay(10)

        self.assertEqual(result, 300)
        mock_uniform.assert_called_once_with(0.8, 1.2)

    @override_settings(
        NOTIFICATION_RETRY_BASE_DELAY=60,
        NOTIFICATION_RETRY_MAX_DELAY=3600,
        NOTIFICATION_RETRY_JITTER=0.2,
    )
    @patch("notifications.processor.random.uniform", return_value=1.2)
    def test_calculate_retry_delay_applies_jitter(self, mock_uniform):
        result = DeliveryProcessor.calculate_retry_delay(1)

        self.assertEqual(result, 72)
        mock_uniform.assert_called_once_with(0.8, 1.2)

    @override_settings(
        NOTIFICATION_MAX_ATTEMPTS=5,
        NOTIFICATION_RETRY_BASE_DELAY=60,
        NOTIFICATION_RETRY_MAX_DELAY=3600,
        NOTIFICATION_RETRY_JITTER=0.2,
    )
    @patch(
        "notifications.processor.random.uniform",
        return_value=1.0,
    )
    def test_schedule_retry_returns_delivery_to_pending(
        self,
        mock_uniform,
    ):
        token = "12345678-1234-5678-1234-567812345678"

        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=2,
            claim_token=token,
            locked_until=timezone.now() + timedelta(minutes=1),
            dispatch_locked_until=timezone.now() + timedelta(minutes=1),
        )

        before_retry = timezone.now()

        result = DeliveryProcessor.schedule_retry(
            delivery.pk,
            token,
            "Temporary SMTP error",
        )

        after_retry = timezone.now()

        self.assertTrue(result)
        mock_uniform.assert_called_once_with(0.8, 1.2)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PENDING,
        )

        expected_delay = timedelta(seconds=120)

        self.assertGreaterEqual(
            delivery.next_attempt_at,
            before_retry + expected_delay,
        )
        self.assertLessEqual(
            delivery.next_attempt_at,
            after_retry + expected_delay,
        )

        self.assertEqual(delivery.last_error, "Temporary SMTP error")
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)
        self.assertIsNone(delivery.dispatch_locked_until)

    @override_settings(NOTIFICATION_MAX_ATTEMPTS=5)
    def test_schedule_retry_fails_when_attempt_limit_reached(self):
        token = "12345678-1234-5678-1234-567812345678"

        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=5,
            claim_token=token,
            locked_until=timezone.now() + timedelta(minutes=1),
            dispatch_locked_until=timezone.now() + timedelta(minutes=1),
        )

        result = DeliveryProcessor.schedule_retry(
            delivery.pk,
            token,
            "Temporary SMTP error",
        )

        self.assertTrue(result)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.FAILED,
        )
        self.assertIsNone(delivery.next_attempt_at)
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)
        self.assertIsNone(delivery.dispatch_locked_until)

    def test_schedule_retry_rejects_stale_token(self):
        old_token = "12345678-1234-5678-1234-567812345678"
        current_token = "87654321-4321-8765-4321-876543218765"

        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=2,
            claim_token=current_token,
            locked_until=timezone.now() + timedelta(minutes=1),
        )

        result = DeliveryProcessor.schedule_retry(
            delivery.pk,
            old_token,
            "Temporary SMTP error",
        )

        self.assertFalse(result)

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PROCESSING,
        )
        self.assertEqual(str(delivery.claim_token), current_token)

    @override_settings(NOTIFICATION_MAX_ATTEMPTS=5)
    def test_schedule_retry_truncates_long_error(self):
        token = "12345678-1234-5678-1234-567812345678"

        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=5,
            claim_token=token,
        )

        long_error = "E" * 5000

        result = DeliveryProcessor.schedule_retry(
            delivery.pk,
            token,
            long_error,
        )

        self.assertTrue(result)

        delivery.refresh_from_db()

        self.assertEqual(len(delivery.last_error), 4000)

    def test_mark_failed_updates_delivery_with_valid_claim_token(self):
        """Постоянная ошибка переводит доставку в FAILED."""
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
        )
        claim_token = delivery.claim_token

        result = DeliveryProcessor.mark_failed(
            delivery.id,
            claim_token,
            PermanentDeliveryError("Invalid recipient"),
        )

        self.assertTrue(result)

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.FAILED,
        )
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)
        self.assertIsNone(delivery.next_attempt_at)
        self.assertIsNone(delivery.dispatch_locked_until)
        self.assertEqual(delivery.last_error, "Invalid recipient")

    def test_mark_failed_rejects_stale_claim_token(self):
        """Устаревший worker не может завершить чужую доставку."""
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
        )

        result = DeliveryProcessor.mark_failed(
            delivery.id,
            uuid.uuid4(),
            PermanentDeliveryError("Invalid recipient"),
        )

        self.assertFalse(result)

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PROCESSING,
        )

    def test_mark_failed_rejects_non_processing_delivery(self):
        """Доставку не в PROCESSING нельзя завершить этим методом."""
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.SENT,
        )

        result = DeliveryProcessor.mark_failed(
            delivery.id,
            delivery.claim_token,
            PermanentDeliveryError("Invalid recipient"),
        )

        self.assertFalse(result)

    def test_claim_processing_delivery_with_null_locked_until(self):
        """PROCESSING без lease можно повторно захватить."""
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
        )
        delivery.locked_until = None
        delivery.save(update_fields=["locked_until"])

        claimed = DeliveryProcessor.claim_delivery(delivery.id)

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.id, delivery.id)
        self.assertEqual(
            claimed.status,
            NotificationDelivery.Status.PROCESSING,
        )
        self.assertIsNotNone(claimed.claim_token)
        self.assertIsNotNone(claimed.locked_until)
        self.assertEqual(claimed.attempts_count, delivery.attempts_count + 1)

    def test_null_lease_processing_delivery_with_exhausted_attempts_is_failed(self):
        """PROCESSING без lease и с исчерпанными попытками завершается."""
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=settings.NOTIFICATION_MAX_ATTEMPTS,
        )
        delivery.locked_until = None
        delivery.save(update_fields=["locked_until"])

        failed_count = DeliveryProcessor.fail_exhausted_deliveries()

        self.assertEqual(failed_count, 1)

        delivery.refresh_from_db()
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.FAILED,
        )
        self.assertIsNone(delivery.claim_token)
        self.assertIsNone(delivery.locked_until)
        self.assertIsNone(delivery.next_attempt_at)


class NotificationModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Еда",
        )

        self.budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

    def test_create_budget_exceeded_notification(self):
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            title="Budget exceeded",
            message="You have exceeded your budget for Еда.",
            budget=self.budget,
        )

        self.assertEqual(
            Notification.objects.count(),
            1,
        )

        self.assertEqual(
            notification.user,
            self.user,
        )

        self.assertEqual(
            notification.budget,
            self.budget,
        )

        self.assertEqual(
            notification.notification_type,
            Notification.NotificationType.BUDGET_EXCEEDED,
        )

        self.assertFalse(
            notification.is_read,
        )

    def test_different_events_for_same_budget_can_be_created(self):
        """
        Один бюджет может иметь несколько уведомлений одного типа,
        если они относятся к разным бизнес-событиям.
        """
        first_notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            event_key=f"budget:{self.budget.id}:exceeded:occurrence-1",
            title="Budget exceeded",
            message="First budget exceeded event.",
            budget=self.budget,
        )

        second_notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            event_key=f"budget:{self.budget.id}:exceeded:occurrence-2",
            title="Budget exceeded again",
            message="Second budget exceeded event.",
            budget=self.budget,
        )

        self.assertNotEqual(
            first_notification.id,
            second_notification.id,
        )

        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                budget=self.budget,
                notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            ).count(),
            2,
        )

    def test_different_budget_can_have_notification(self):
        second_category = Category.objects.create(
            user=self.user,
            name="Транспорт",
        )

        second_budget = Budget.objects.create(
            user=self.user,
            category=second_category,
            amount="5000.00",
            month="2026-08-01",
        )

        Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            title="Budget exceeded",
            message="Food budget exceeded.",
            budget=self.budget,
        )

        Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            title="Budget exceeded",
            message="Transport budget exceeded.",
            budget=second_budget,
        )

        self.assertEqual(
            Notification.objects.count(),
            2,
        )

    def test_notification_belongs_to_user(self):
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            title="Budget exceeded",
            message="You have exceeded your budget.",
            budget=self.budget,
        )

        self.assertEqual(
            notification.user,
            self.budget.user,
        )

        self.assertEqual(
            notification.budget.user,
            self.user,
        )

class NotificationAPITest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="api_user",
            password="testpass123",
        )

        self.other_user = User.objects.create_user(
            username="other_user",
            password="testpass123",
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Еда",
        )

        self.budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-09-01",
        )

        self.notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            title="Budget exceeded",
            message="Your budget has been exceeded.",
            budget=self.budget,
        )

        self.other_category = Category.objects.create(
            user=self.other_user,
            name="Еда",
        )

        self.other_budget = Budget.objects.create(
            user=self.other_user,
            category=self.other_category,
            amount="5000.00",
            month="2026-09-01",
        )

        self.other_notification = Notification.objects.create(
            user=self.other_user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            title="Other budget exceeded",
            message="Other user notification.",
            budget=self.other_budget,
        )

        self.url = "/api/v1/notifications/"

    def test_authenticated_user_can_list_own_notifications(self):
        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            self.notification.id,
        )

    def test_user_cannot_see_other_users_notifications(self):
        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        notification_ids = [
            item["id"]
            for item in response.data["results"]
        ]

        self.assertNotIn(
            self.other_notification.id,
            notification_ids,
        )

    def test_unauthenticated_user_cannot_access_notifications(self):
        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_user_can_mark_notification_as_read(self):
        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.patch(
            f"{self.url}{self.notification.id}/",
            {
                "is_read": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.notification.refresh_from_db()

        self.assertTrue(
            self.notification.is_read,
        )

    def test_read_only_fields_cannot_be_changed(self):
        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.patch(
            f"{self.url}{self.notification.id}/",
            {
                "title": "Hacked title",
                "message": "Hacked message",
                "notification_type": "something_else",
                "budget": None,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.notification.refresh_from_db()

        self.assertEqual(
            self.notification.title,
            "Budget exceeded",
        )

        self.assertEqual(
            self.notification.message,
            "Your budget has been exceeded.",
        )

        self.assertEqual(
            self.notification.notification_type,
            Notification.NotificationType.BUDGET_EXCEEDED,
        )

        self.assertEqual(
            self.notification.budget,
            self.budget,
        )

    def test_user_cannot_modify_other_users_notification(self):
        self.client.force_authenticate(
            user=self.user,
        )

        response = self.client.patch(
            f"{self.url}{self.other_notification.id}/",
            {
                "is_read": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.other_notification.refresh_from_db()

        self.assertFalse(
            self.other_notification.is_read,
        )


class NotificationServiceTest(TestCase):
    """
    Проверяет централизованное создание уведомлений.

    Тесты защищают от дублирования событий и проверяют,
    что язык и данные сохраняются на момент создания.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="service_user",
            password="testpass123",
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Еда",
        )

        self.budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

    def test_create_notification(self):
        """
        Проверяет создание нового уведомления и сохранение данных.
        """
        data = {
            "budget_id": self.budget.id,
            "budget_amount": "10000.00",
            "spent_amount": "12000.00",
            "currency": "CZK",
        }

        notification, created = NotificationService.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            event_key=f"budget:{self.budget.id}:budget_exceeded",
            title="Budget exceeded",
            message="Your budget has been exceeded.",
            data=data,
            budget=self.budget,
        )

        self.assertTrue(created)
        self.assertIsNotNone(notification.pk)
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.budget, self.budget)
        self.assertEqual(notification.data, data)
        self.assertEqual(notification.locale, "en")
        self.assertEqual(Notification.objects.count(), 1)

    def test_same_event_key_does_not_create_duplicate(self):
        """
        Повторная обработка одного события не создаёт дубликат.
        """
        event_key = f"budget:{self.budget.id}:budget_exceeded"

        first_notification, first_created = NotificationService.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            event_key=event_key,
            title="Budget exceeded",
            message="Your budget has been exceeded.",
            budget=self.budget,
        )

        second_notification, second_created = NotificationService.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            event_key=event_key,
            title="Another title",
            message="Another message.",
            budget=self.budget,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_notification.id, second_notification.id)
        self.assertEqual(Notification.objects.count(), 1)

    def test_same_event_key_can_be_used_by_different_users(self):
        """
        Один event_key может существовать у разных пользователей.
        """
        other_user = User.objects.create_user(
            username="another_service_user",
            password="testpass123",
        )

        event_key = "expense:123:created"

        first_notification, first_created = NotificationService.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key=event_key,
            title="Expense created",
            message="Expense created.",
        )

        second_notification, second_created = NotificationService.create(
            user=other_user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key=event_key,
            title="Expense created",
            message="Expense created.",
        )

        self.assertTrue(first_created)
        self.assertTrue(second_created)
        self.assertNotEqual(first_notification.id, second_notification.id)
        self.assertEqual(Notification.objects.count(), 2)

    def test_notification_saves_user_language(self):
        """
        Язык пользователя сохраняется в уведомлении.
        """
        UserSettings.objects.update_or_create(
            user=self.user,
            defaults={"language": "ru"},
        )

        notification, created = NotificationService.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="expense:456:created",
            title="Расход создан",
            message="Новый расход добавлен.",
        )

        self.assertTrue(created)
        self.assertEqual(notification.locale, "ru")

    def test_missing_user_settings_uses_english(self):
        """
        Если настройки пользователя отсутствуют, используется en.
        """
        UserSettings.objects.filter(user=self.user).delete()

        notification, created = NotificationService.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="expense:789:created",
            title="Expense created",
            message="Expense created.",
        )

        self.assertTrue(created)
        self.assertEqual(notification.locale, "en")

    def test_different_event_keys_create_separate_notifications_for_same_budget(self):
        """
        Разные бизнес-события одного бюджета создают отдельные уведомления.
        """
        first_notification, first_created = NotificationService.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            event_key=f"budget:{self.budget.id}:occurrence-1",
            title="Budget exceeded",
            message="First budget exceeded event.",
            budget=self.budget,
        )

        second_notification, second_created = NotificationService.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            event_key=f"budget:{self.budget.id}:occurrence-2",
            title="Budget exceeded again",
            message="Second budget exceeded event.",
            budget=self.budget,
        )

        self.assertTrue(first_created)
        self.assertTrue(second_created)
        self.assertNotEqual(first_notification.id, second_notification.id)

        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                budget=self.budget,
                notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            ).count(),
            2,
        )

    def test_empty_event_key_is_rejected(self):
        """
        Сервис не должен создавать события без ключа идемпотентности.
        """
        with self.assertRaises(ValueError):
            NotificationService.create(
                user=self.user,
                notification_type=Notification.NotificationType.EXPENSE_CREATED,
                event_key="",
                title="Expense created",
                message="Expense created.",
            )

        self.assertEqual(Notification.objects.count(), 0)

    def test_empty_data_dictionary_is_preserved(self):
        """
        Явно переданный пустой словарь сохраняется как пустой JSON-объект.
        """
        notification, created = NotificationService.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="expense:empty-data:created",
            title="Expense created",
            message="Expense created.",
            data={},
        )

        self.assertTrue(created)
        self.assertEqual(notification.data, {})


class DeliveryServiceTest(TestCase):
    """
    Проверяет создание записей доставки уведомлений.

    Тесты контролируют пользовательские настройки EMAIL,
    наличие адреса получателя и сохранение его снимка.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="delivery_user",
            password="testpass123",
            email="delivery@example.com",
        )

        self.notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="expense:delivery-test",
            title="Expense created",
            message="A new expense was created.",
        )

    def test_email_delivery_is_created_with_recipient_snapshot(self):
        """
        При включённом EMAIL создаётся доставка
        с сохранённым адресом получателя.
        """
        deliveries = DeliveryService.create_deliveries(
            self.notification,
        )

        self.assertEqual(len(deliveries), 1)

        delivery = deliveries[0]

        self.assertEqual(
            delivery.channel,
            NotificationDelivery.Channel.EMAIL,
        )
        self.assertEqual(
            delivery.recipient,
            "delivery@example.com",
        )
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PENDING,
        )

    def test_email_delivery_uses_trimmed_recipient(self):
        """
        Пробелы вокруг email не должны попадать
        в сохранённый адрес получателя.
        """
        self.user.email = "  delivery@example.com  "
        self.user.save(update_fields=["email"])

        deliveries = DeliveryService.create_deliveries(
            self.notification,
        )

        self.assertEqual(
            deliveries[0].recipient,
            "delivery@example.com",
        )

    def test_email_delivery_is_not_created_when_disabled(self):
        """
        Отключённый EMAIL-канал не создаёт запись доставки.
        """
        NotificationSettings.objects.create(
            user=self.user,
            email_enabled=False,
        )

        deliveries = DeliveryService.create_deliveries(
            self.notification,
        )

        self.assertEqual(deliveries, [])
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    def test_email_delivery_is_not_created_without_recipient(self):
        """
        Без email-адреса невозможно подготовить EMAIL-доставку.
        """
        self.user.email = ""
        self.user.save(update_fields=["email"])

        deliveries = DeliveryService.create_deliveries(
            self.notification,
        )

        self.assertEqual(deliveries, [])
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    def test_missing_settings_use_default_email_preference(self):
        """
        Для старых пользователей без NotificationSettings
        применяется default email_enabled=True.
        """
        deliveries = DeliveryService.create_deliveries(
            self.notification,
        )

        self.assertEqual(len(deliveries), 1)
        self.assertEqual(
            deliveries[0].recipient,
            "delivery@example.com",
        )

    def test_existing_delivery_recipient_is_not_overwritten(self):
        """
        Повторная подготовка доставки не меняет первоначальный
        снимок адреса получателя.
        """
        delivery = NotificationDelivery.objects.create(
            notification=self.notification,
            channel=NotificationDelivery.Channel.EMAIL,
            recipient="original@example.com",
        )

        self.user.email = "new@example.com"
        self.user.save(update_fields=["email"])

        deliveries = DeliveryService.create_deliveries(
            self.notification,
        )

        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].id, delivery.id)
        self.assertEqual(
            deliveries[0].recipient,
            "original@example.com",
        )


class NotificationOrchestratorTest(TestCase):
    """
    Проверяет совместное создание уведомлений и доставок.

    Тесты защищают атомарность операций, идемпотентность
    и применение пользовательских настроек.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="orchestrator_user",
            password="testpass123",
            email="orchestrator@example.com",
        )

    def _create_notification(self, **overrides):
        """
        Создаёт уведомление через оркестратор.

        Общие параметры вынесены в helper, чтобы тесты
        проверяли поведение, а не повторяли подготовку данных.
        """
        params = {
            "user": self.user,
            "notification_type": Notification.NotificationType.EXPENSE_CREATED,
            "event_key": "expense:orchestrator-test",
            "title": "Expense created",
            "message": "A new expense was created.",
        }
        params.update(overrides)

        return NotificationOrchestrator.create(**params)

    def test_new_notification_creates_email_delivery(self):
        """
        Новое уведомление и разрешённая EMAIL-доставка
        создаются совместно.
        """
        notification, created = self._create_notification()

        self.assertTrue(created)
        self.assertIsNotNone(notification)

        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(NotificationDelivery.objects.count(), 1)

        delivery = NotificationDelivery.objects.get(
            notification=notification,
        )

        self.assertEqual(
            delivery.channel,
            NotificationDelivery.Channel.EMAIL,
        )
        self.assertEqual(
            delivery.recipient,
            "orchestrator@example.com",
        )

    def test_notification_is_created_without_email_delivery_when_disabled(self):
        """
        Отключение EMAIL запрещает внешнюю доставку,
        но не отменяет само уведомление в приложении.
        """
        NotificationSettings.objects.create(
            user=self.user,
            email_enabled=False,
        )

        notification, created = self._create_notification()

        self.assertTrue(created)
        self.assertIsNotNone(notification)

        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    def test_duplicate_event_does_not_create_another_delivery(self):
        """
        Повторное событие с тем же event_key возвращает
        существующее уведомление и не создаёт новую доставку.
        """
        first_notification, first_created = self._create_notification()

        second_notification, second_created = self._create_notification()

        self.assertTrue(first_created)
        self.assertFalse(second_created)

        self.assertEqual(
            first_notification.id,
            second_notification.id,
        )
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(NotificationDelivery.objects.count(), 1)

    def test_disabled_daily_summary_is_not_created(self):
        """
        При отключённой daily_summary не создаётся
        ни само уведомление, ни запись доставки.
        """
        NotificationSettings.objects.create(
            user=self.user,
            daily_summary=False,
        )

        notification, created = self._create_notification(
            notification_type=Notification.NotificationType.DAILY_SUMMARY,
            event_key="daily-summary:disabled-test",
        )

        self.assertIsNone(notification)
        self.assertFalse(created)

        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    def test_daily_summary_is_created_when_enabled(self):
        """
        При включённой daily_summary событие создаётся
        обычным образом.
        """
        NotificationSettings.objects.create(
            user=self.user,
            daily_summary=True,
        )

        notification, created = self._create_notification(
            notification_type=Notification.NotificationType.DAILY_SUMMARY,
            event_key="daily-summary:enabled-test",
        )

        self.assertTrue(created)
        self.assertIsNotNone(notification)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(NotificationDelivery.objects.count(), 1)

    def test_missing_settings_use_default_daily_summary_preference(self):
        """
        При отсутствии NotificationSettings применяется
        default daily_summary=True.
        """
        notification, created = self._create_notification(
            notification_type=Notification.NotificationType.DAILY_SUMMARY,
            event_key="daily-summary:default-test",
        )

        self.assertTrue(created)
        self.assertIsNotNone(notification)
        self.assertEqual(Notification.objects.count(), 1)

    def test_delivery_error_rolls_back_notification(self):
        """
        Ошибка при создании доставки должна откатить
        и новое уведомление благодаря общей транзакции.
        """
        with patch(
            "notifications.orchestrators.DeliveryService.create_deliveries",
            side_effect=RuntimeError("Delivery creation failed"),
        ):
            with self.assertRaises(RuntimeError):
                self._create_notification()

        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(NotificationDelivery.objects.count(), 0)


class NotificationServiceConcurrencyTest(TransactionTestCase):
    """
    Проверяет конкурентное создание уведомлений через PostgreSQL.

    Каждый поток использует собственное соединение с БД.
    Barrier синхронизирует потоки непосредственно перед INSERT,
    чтобы воспроизвести ситуацию одновременного создания событий.
    """

    reset_sequences = True

    def setUp(self):
        self.user = User.objects.create_user(
            username="concurrent_user",
            password="testpass123",
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Еда",
        )

        self.budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

    @staticmethod
    def _create_notification_in_thread(
        user_id,
        budget_id,
        event_key,
    ):
        """
        Создаёт уведомление в отдельном потоке.

        Объекты пользователя и бюджета загружаются заново,
        чтобы потоки не использовали общие ORM-объекты.
        """
        close_old_connections()

        try:
            user = User.objects.get(pk=user_id)
            budget = Budget.objects.get(pk=budget_id)

            notification, created = NotificationService.create(
                user=user,
                notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
                event_key=event_key,
                title="Budget exceeded",
                message="Your budget has been exceeded.",
                budget=budget,
            )

            return notification.pk, created

        finally:
            close_old_connections()

    def _run_concurrent_creations(self, event_keys):
        """
        Запускает два конкурентных создания уведомлений.

        Оба потока должны дойти до INSERT прежде, чем
        любой из них продолжит выполнение.
        """
        barrier = Barrier(2)
        original_create = Notification.objects.create

        def synchronized_create(*args, **kwargs):
            barrier.wait(timeout=10)
            return original_create(*args, **kwargs)

        with patch.object(
            Notification.objects,
            "create",
            side_effect=synchronized_create,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        self._create_notification_in_thread,
                        self.user.pk,
                        self.budget.pk,
                        event_key,
                    )
                    for event_key in event_keys
                ]

                return [
                    future.result(timeout=20)
                    for future in futures
                ]

    def test_concurrent_same_event_key_creates_only_one_notification(self):
        """
        Одинаковый event_key в двух потоках не создаёт дубликат.

        Уникальное ограничение PostgreSQL защищает от гонки:
        один поток создаёт запись, второй получает существующую.
        """
        event_key = f"budget:{self.budget.pk}:concurrent-event"

        results = self._run_concurrent_creations([
            event_key,
            event_key,
        ])

        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                event_key=event_key,
            ).count(),
            1,
        )

        self.assertEqual(
            sorted(created for _, created in results),
            [False, True],
        )

        self.assertEqual(
            results[0][0],
            results[1][0],
        )

    def test_concurrent_different_event_keys_for_same_budget(self):
        """
        Разные события одного бюджета могут создаваться параллельно.

        Удалённое legacy-ограничение не должно блокировать
        создание второго уведомления.
        """
        event_keys = [
            f"budget:{self.budget.pk}:occurrence-1",
            f"budget:{self.budget.pk}:occurrence-2",
        ]

        results = self._run_concurrent_creations(event_keys)

        self.assertEqual(
            sorted(created for _, created in results),
            [True, True],
        )

        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                budget=self.budget,
                notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            ).count(),
            2,
        )

        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                event_key__in=event_keys,
            ).count(),
            2,
        )



class NotificationDispatcherTest(TestCase):
    """
    Проверяет выбор и резервирование доставок периодическим dispatcher.

    Celery broker не используется: публикация задач заменяется mock.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="dispatcher_test_user",
            email="dispatcher@example.com",
            password="testpass123",
        )

        self.notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="dispatcher:test:event",
            title="Dispatcher test",
            message="Dispatcher test message",
        )

    def create_delivery(self, **kwargs):
        """
        Создаёт доставку для проверки сценариев dispatcher.
        """
        return NotificationDelivery.objects.create(
            notification=self.notification,
            channel=NotificationDelivery.Channel.EMAIL,
            recipient="recipient@example.com",
            **kwargs,
        )

    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_dispatches_ready_pending_delivery(self, mock_delay):
        """
        Готовая PENDING-доставка резервируется и публикуется в Celery.
        """
        delivery = self.create_delivery()

        result = dispatch_pending_deliveries()

        self.assertEqual(
            result,
            {
                "selected": 1,
                "dispatched": 1,
                "failed": 0,
            },
        )

        mock_delay.assert_called_once_with(delivery.pk)

        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.dispatch_locked_until)

    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_does_not_dispatch_delivery_with_future_retry(
        self,
        mock_delay,
    ):
        """
        Доставка с будущим next_attempt_at пока не публикуется.
        """
        delivery = self.create_delivery(
            next_attempt_at=timezone.now() + timedelta(minutes=5),
        )

        result = dispatch_pending_deliveries()

        self.assertEqual(result["selected"], 0)
        self.assertEqual(result["dispatched"], 0)
        mock_delay.assert_not_called()

        delivery.refresh_from_db()
        self.assertIsNone(delivery.dispatch_locked_until)

    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_does_not_dispatch_delivery_with_active_reservation(
        self,
        mock_delay,
    ):
        """
        Доставка с действующей dispatcher reservation не выбирается.
        """
        delivery = self.create_delivery(
            dispatch_locked_until=timezone.now() + timedelta(minutes=2),
        )

        result = dispatch_pending_deliveries()

        self.assertEqual(result["selected"], 0)
        self.assertEqual(result["dispatched"], 0)
        mock_delay.assert_not_called()

        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.dispatch_locked_until)

    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_dispatches_delivery_with_expired_reservation(
        self,
        mock_delay,
    ):
        """
        Доставка с истёкшей dispatcher reservation может быть выбрана снова.
        """
        delivery = self.create_delivery(
            dispatch_locked_until=timezone.now() - timedelta(seconds=1),
        )

        result = dispatch_pending_deliveries()

        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["dispatched"], 1)
        mock_delay.assert_called_once_with(delivery.pk)

        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.dispatch_locked_until)

    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_releases_reservation_when_publish_fails(
        self,
        mock_delay,
    ):
        """
        При ошибке публикации reservation освобождается.
        """
        delivery = self.create_delivery()
        mock_delay.side_effect = RuntimeError("Broker unavailable")

        result = dispatch_pending_deliveries()

        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["dispatched"], 0)
        self.assertEqual(result["failed"], 1)

        delivery.refresh_from_db()
        self.assertIsNone(delivery.dispatch_locked_until)

    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_continues_dispatching_after_publish_failure(
        self,
        mock_delay,
    ):
        """
        Ошибка публикации одной доставки не останавливает остальные.
        """
        first = self.create_delivery()

        second_notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="dispatcher:test:second:event",
            title="Second dispatcher test",
            message="Second dispatcher test message",
        )

        second = NotificationDelivery.objects.create(
            notification=second_notification,
            channel=NotificationDelivery.Channel.EMAIL,
            recipient="second@example.com",
        )

        mock_delay.side_effect = [
            RuntimeError("Broker unavailable"),
            None,
        ]

        result = dispatch_pending_deliveries()

        self.assertEqual(
            result,
            {
                "selected": 2,
                "dispatched": 1,
                "failed": 1,
            },
        )

        self.assertEqual(mock_delay.call_count, 2)

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertIsNone(first.dispatch_locked_until)
        self.assertIsNotNone(second.dispatch_locked_until)

    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_dispatches_processing_delivery_with_expired_lease(
        self,
        mock_delay,
    ):
        """
        Dispatcher повторно публикует доставку с истёкшим worker lease.
        """
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=1,
            locked_until=timezone.now() - timedelta(seconds=1),
        )

        result = dispatch_pending_deliveries()

        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["dispatched"], 1)
        mock_delay.assert_called_once_with(delivery.pk)

        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.dispatch_locked_until)

    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_does_not_dispatch_processing_delivery_with_active_lease(
        self,
        mock_delay,
    ):
        """
        Доставка с действующим worker lease не публикуется повторно.
        """
        delivery = self.create_delivery(
            status=NotificationDelivery.Status.PROCESSING,
            attempts_count=1,
            locked_until=timezone.now() + timedelta(minutes=2),
        )

        result = dispatch_pending_deliveries()

        self.assertEqual(result["selected"], 0)
        self.assertEqual(result["dispatched"], 0)
        mock_delay.assert_not_called()

        delivery.refresh_from_db()
        self.assertIsNone(delivery.dispatch_locked_until)

    @patch("notifications.tasks.DISPATCH_BATCH_SIZE", 2)
    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_dispatches_only_up_to_batch_limit(
        self,
        mock_delay,
    ):
        """
        Dispatcher выбирает не больше доставок, чем разрешает batch limit.

        Третья доставка остаётся PENDING и без reservation,
        чтобы её мог обработать следующий запуск dispatcher.
        """
        first = self.create_delivery()

        second_notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="dispatcher:test:batch:second",
            title="Second batch notification",
            message="Second batch notification message",
        )

        second = NotificationDelivery.objects.create(
            notification=second_notification,
            channel=NotificationDelivery.Channel.EMAIL,
            recipient="second@example.com",
        )

        third_notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="dispatcher:test:batch:third",
            title="Third batch notification",
            message="Third batch notification message",
        )

        third = NotificationDelivery.objects.create(
            notification=third_notification,
            channel=NotificationDelivery.Channel.EMAIL,
            recipient="third@example.com",
        )

        result = dispatch_pending_deliveries()

        self.assertEqual(
            result,
            {
                "selected": 2,
                "dispatched": 2,
                "failed": 0,
            },
        )

        self.assertEqual(mock_delay.call_count, 2)

        dispatched_ids = {
            call.args[0]
            for call in mock_delay.call_args_list
        }

        self.assertEqual(
            dispatched_ids,
            {first.pk, second.pk},
        )

        first.refresh_from_db()
        second.refresh_from_db()
        third.refresh_from_db()

        self.assertIsNotNone(first.dispatch_locked_until)
        self.assertIsNotNone(second.dispatch_locked_until)

        self.assertIsNone(third.dispatch_locked_until)
        self.assertEqual(
            third.status,
            NotificationDelivery.Status.PENDING,
        )


class NotificationDispatcherConcurrencyTest(TransactionTestCase):
    """
    Проверяет конкурентную работу нескольких dispatcher-процессов.

    Два потока одновременно пытаются зарезервировать одну готовую
    доставку. PostgreSQL select_for_update(skip_locked=True) и
    dispatch_locked_until должны гарантировать, что Celery-задача
    будет опубликована только одним из dispatcher.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="dispatcher_concurrent_user",
            email="dispatcher_concurrent@example.com",
            password="testpass123",
        )

        self.notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="dispatcher:concurrent:event",
            title="Concurrent dispatcher test",
            message="Concurrent dispatcher test message",
        )

        self.delivery = NotificationDelivery.objects.create(
            notification=self.notification,
            channel=NotificationDelivery.Channel.EMAIL,
            recipient="recipient@example.com",
        )

    @staticmethod
    def _run_dispatcher(barrier):
        """
        Запускает dispatcher в отдельном потоке.

        Каждый поток получает собственное соединение PostgreSQL.
        Barrier позволяет начать проверку конкурентного доступа
        практически одновременно.
        """
        close_old_connections()

        try:
            barrier.wait(timeout=10)
            return dispatch_pending_deliveries()
        finally:
            close_old_connections()

    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_concurrent_dispatchers_enqueue_delivery_only_once(
        self,
        mock_delay,
    ):
        """
        Два параллельных dispatcher не должны опубликовать
        одну и ту же доставку дважды.
        """
        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._run_dispatcher, barrier)
                for _ in range(2)
            ]

            results = [
                future.result(timeout=20)
                for future in futures
            ]

        self.assertEqual(
            sum(result["selected"] for result in results),
            1,
        )

        self.assertEqual(
            sum(result["dispatched"] for result in results),
            1,
        )

        self.assertEqual(
            sum(result["failed"] for result in results),
            0,
        )

        mock_delay.assert_called_once_with(self.delivery.pk)

        self.delivery.refresh_from_db()
        self.assertIsNotNone(self.delivery.dispatch_locked_until)


class NotificationDispatcherTransactionTest(TransactionTestCase):
    """
    Проверяет, что Celery-задачи публикуются после завершения
    транзакции резервирования доставок.

    Это позволяет не удерживать блокировки PostgreSQL во время
    обращения к брокеру сообщений.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="dispatcher_transaction_user",
            email="dispatcher_transaction@example.com",
            password="testpass123",
        )

        self.notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_CREATED,
            event_key="dispatcher:transaction:event",
            title="Transaction test",
            message="Transaction test message",
        )

        self.delivery = NotificationDelivery.objects.create(
            notification=self.notification,
            channel=NotificationDelivery.Channel.EMAIL,
            recipient="recipient@example.com",
        )

    @patch("notifications.tasks.process_notification_delivery.delay")
    def test_publishes_task_after_reservation_transaction_commits(
        self,
        mock_delay,
    ):
        """
        В момент публикации задача уже зарезервирована в БД,
        а транзакция резервирования завершена.
        """
        observed = {}

        def inspect_publication(delivery_id):
            observed["in_atomic_block"] = connection.in_atomic_block

            persisted_delivery = NotificationDelivery.objects.get(
                pk=delivery_id,
            )
            observed["dispatch_locked_until"] = (
                persisted_delivery.dispatch_locked_until
            )

        mock_delay.side_effect = inspect_publication

        result = dispatch_pending_deliveries()

        self.assertEqual(
            result,
            {
                "selected": 1,
                "dispatched": 1,
                "failed": 0,
            },
        )

        mock_delay.assert_called_once_with(self.delivery.pk)

        # Публикация выполняется вне transaction.atomic().
        self.assertFalse(observed["in_atomic_block"])

        # Reservation уже сохранена до обращения к Celery.
        self.assertIsNotNone(observed["dispatch_locked_until"])

        self.delivery.refresh_from_db()
        self.assertIsNotNone(self.delivery.dispatch_locked_until)
