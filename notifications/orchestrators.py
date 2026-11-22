"""
Оркестрация создания уведомлений и записей доставки.

NotificationService отвечает за создание бизнес-события.
DeliveryService отвечает за подготовку каналов доставки.

NotificationOrchestrator объединяет эти операции в одной
транзакции, чтобы уведомление не могло сохраниться без
предусмотренных для него записей доставки.
"""

from django.db import transaction

from users.models import NotificationSettings

from .delivery import DeliveryService
from .models import Notification
from .services import NotificationService


class NotificationOrchestrator:
    """
    Координирует создание уведомления и его доставок.

    Сохраняет интерфейс NotificationService.create():
        (notification, created)

    Новые доставки создаются только вместе с новым уведомлением.
    Повторная обработка того же event_key не создаёт дубликатов.

    Если пользователь отключил определённый тип уведомлений,
    соответствующее событие не создаётся.
    """

    @staticmethod
    def _is_notification_enabled(user, notification_type):
        """
        Проверяет, разрешено ли создание конкретного типа уведомления.

        daily_summary является настройкой типа события, а не канала
        доставки. Поэтому при отключённых сводках не создаём само
        уведомление — ни в приложении, ни для внешних каналов.

        Если настройки пользователя отсутствуют, применяются
        значения по умолчанию модели NotificationSettings.
        """
        if (
            notification_type
            != Notification.NotificationType.DAILY_SUMMARY
        ):
            return True

        try:
            notification_settings = user.notification_settings
        except NotificationSettings.DoesNotExist:
            return True

        return notification_settings.daily_summary

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        user,
        notification_type,
        event_key,
        title,
        message,
        data=None,
        budget=None,
    ):
        """
        Атомарно создаёт уведомление и подходящие записи доставки.

        Если тип уведомления отключён пользователем, возвращает
        (None, False), не создавая ни уведомление, ни доставку.

        Если бизнес-событие уже существует, возвращает его
        без повторного создания доставок.

        Если создание доставки завершается ошибкой, транзакция
        откатывает также новое уведомление.

        Возвращает:
            (notification, created)

            notification может быть None, если тип уведомления
            отключён пользовательскими настройками.
        """
        # Сначала проверяем настройки типа события.
        # Например, отключённая daily_summary не должна создавать
        # даже внутреннее уведомление в приложении.
        if not cls._is_notification_enabled(user, notification_type):
            return None, False

        # Создание бизнес-события остаётся ответственностью
        # NotificationService. Его механизм идемпотентности
        # защищает от повторного создания одного события.
        notification, created = NotificationService.create(
            user=user,
            notification_type=notification_type,
            event_key=event_key,
            title=title,
            message=message,
            data=data,
            budget=budget,
        )

        # Записи доставки создаём только для нового уведомления.
        # Повторная обработка существующего event_key не должна
        # повторно менять первоначальный набор каналов доставки.
        if created:
            DeliveryService.create_deliveries(notification)

        return notification, created
