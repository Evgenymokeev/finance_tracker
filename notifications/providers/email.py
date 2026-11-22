"""
Email-провайдер доставки уведомлений.

Использует стандартный Django email backend, настройки которого
задаются через EMAIL_HOST, EMAIL_PORT и другие параметры проекта.

Провайдер отвечает только за отправку сообщения.
Изменение статусов NotificationDelivery и управление retry
выполняются отдельным DeliveryProcessor.
"""


import smtplib
import socket

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import BadHeaderError, send_mail

from .base import (
    BaseSender,
    PermanentDeliveryError,
    TemporaryDeliveryError,
)


class EmailSender(BaseSender):
    """
    Отправляет уведомления по электронной почте.

    Адрес получателя берётся из NotificationDelivery.recipient,
    чтобы изменение email пользователя не влияло на уже созданную
    доставку.

    Провайдер не изменяет состояние записи доставки.
    """

    @staticmethod
    def _classify_smtp_error(error, message):
        """
        Преобразует SMTP-ответ в типизированную ошибку доставки.

        Коды 4xx означают временный отказ.
        Коды 5xx означают постоянный отказ.

        Если SMTP не предоставил код ответа, такая ошибка
        классифицируется как постоянная только в тех случаях,
        где это обосновано типом исключения.
        """
        smtp_code = getattr(error, "smtp_code", None)

        if smtp_code is not None and 400 <= smtp_code < 500:
            raise TemporaryDeliveryError(message) from error

        raise PermanentDeliveryError(message) from error

    def send(self, delivery):
        """
        Отправляет email с содержимым связанного уведомления.

        Возвращает:
            Количество сообщений, переданных email backend.

        Исключения:
            TemporaryDeliveryError: временная ошибка SMTP или сети.
            PermanentDeliveryError: постоянная ошибка отправки.
        """
        recipient = (delivery.recipient or "").strip()

        if not recipient:
            raise PermanentDeliveryError(
                "Email recipient is empty."
            )

        notification = delivery.notification

        if not settings.EMAIL_HOST:
            raise PermanentDeliveryError(
                "Email SMTP host is not configured."
            )

        try:
            sent_count = send_mail(
                subject=notification.title,
                message=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )

        except BadHeaderError as exc:
            raise PermanentDeliveryError(
                "Email contains an invalid header."
            ) from exc

        except ImproperlyConfigured as exc:
            raise PermanentDeliveryError(
                "Email backend is incorrectly configured."
            ) from exc

        except smtplib.SMTPAuthenticationError as exc:
            self._classify_smtp_error(
                exc,
                "SMTP authentication failed.",
            )

        except smtplib.SMTPRecipientsRefused as exc:
            # SMTPRecipientsRefused хранит коды отказа отдельно
            # для каждого адреса получателя.
            #
            # Если все адреса отклонены временными кодами 4xx,
            # допускаем повторную отправку.
            response_codes = [
                response[0]
                for response in exc.recipients.values()
            ]

            if response_codes and all(
                400 <= code < 500
                for code in response_codes
            ):
                raise TemporaryDeliveryError(
                    "SMTP server temporarily refused recipient."
                ) from exc

            raise PermanentDeliveryError(
                "SMTP server permanently refused recipient."
            ) from exc

        except smtplib.SMTPResponseException as exc:
            self._classify_smtp_error(
                exc,
                "SMTP server returned an error.",
            )

        except (
            smtplib.SMTPServerDisconnected,
            smtplib.SMTPConnectError,
            smtplib.SMTPException,
            socket.timeout,
            TimeoutError,
            ConnectionError,
            OSError,
        ) as exc:
            raise TemporaryDeliveryError(
                "Temporary SMTP or network error."
            ) from exc

        if sent_count != 1:
            raise TemporaryDeliveryError(
                "Email backend did not confirm message delivery."
            )

        return sent_count
