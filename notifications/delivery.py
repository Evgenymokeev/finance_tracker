"""
Сервис управления записями доставки уведомлений.

На этом этапе сервис определяет, какие каналы доставки
разрешены пользовательскими настройками, и создаёт
соответствующие NotificationDelivery.

Фактическая отправка сообщений выполняется отдельными
provider-классами и Celery-задачами.
"""

from users.models import NotificationSettings

from .models import NotificationDelivery


class DeliveryService:
    """
    Управляет созданием записей доставки уведомлений.

    Сервис не отправляет сообщения и не отвечает за retry.
    Его задача — зафиксировать намерение доставить уведомление
    через разрешённые и доступные каналы.
    """

    @staticmethod
    def _get_notification_settings(user):
        """
        Возвращает настройки уведомлений пользователя.

        Для старых пользователей запись NotificationSettings
        может отсутствовать. В этом случае используем defaults
        модели, не создавая дополнительную запись в БД.
        """
        try:
            return user.notification_settings
        except NotificationSettings.DoesNotExist:
            return None

    @classmethod
    def create_deliveries(cls, notification):
        """
        Создаёт записи доставки для нового уведомления.

        EMAIL создаётся только при включённой настройке
        и наличии адреса пользователя.

        PUSH и TELEGRAM пока не создаются: для них ещё
        отсутствуют модели подключения и идентификаторы
        получателей.

        Возвращает список созданных или найденных доставок.
        """
        user = notification.user
        notification_settings = cls._get_notification_settings(user)

        # При отсутствии настроек применяем default модели.
        email_enabled = (
            notification_settings.email_enabled
            if notification_settings is not None
            else True
        )

        recipient = (user.email or "").strip()

        # Не создаём доставку без адреса или при отключённом
        # пользователем email-канале.
        if not email_enabled or not recipient:
            return []

        delivery, _ = NotificationDelivery.objects.get_or_create(
            notification=notification,
            channel=NotificationDelivery.Channel.EMAIL,
            defaults={
                "recipient": recipient,
            },
        )

        return [delivery]
