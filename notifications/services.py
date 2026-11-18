"""
Сервис создания уведомлений.

Централизует создание событий, обеспечивает идемпотентность
и сохраняет язык и контекст уведомления на момент его создания.
"""

from django.db import IntegrityError, transaction

from users.models import UserSettings

from .models import Notification


class NotificationService:
    """
    Единая точка создания уведомлений для приложений проекта.

    Сервис не отправляет уведомления по внешним каналам.
    Его ответственность — надёжно сохранить событие в базе.
    """

    @staticmethod
    def _get_user_locale(user):
        """
        Возвращает язык пользователя.

        Настройки могут отсутствовать у старых пользователей,
        поэтому в таком случае используем английский язык.
        """
        try:
            return user.settings.language
        except UserSettings.DoesNotExist:
            return "en"

    @classmethod
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
        Создаёт уведомление или возвращает существующее.

        event_key идентифицирует конкретное бизнес-событие
        и защищает от повторной обработки Celery-задач.

        Возвращает:
            (notification, created)
        """
        if not event_key:
            raise ValueError("event_key must not be empty")

        # Сначала ищем событие по новому универсальному ключу.
        existing = Notification.objects.filter(
            user=user,
            event_key=event_key,
        ).first()

        if existing is not None:
            return existing, False

        # Совместимость с уведомлениями старого формата,
        # созданными до внедрения NotificationService.
        if budget is not None:
            existing = Notification.objects.filter(
                user=user,
                budget=budget,
                notification_type=notification_type,
            ).first()

            if existing is not None:
                # Заполняем ключ у старой записи, если он отсутствует.
                if existing.event_key is None:
                    existing.event_key = event_key
                    existing.save(update_fields=["event_key"])

                return existing, False

        try:
            with transaction.atomic():
                notification = Notification.objects.create(
                    user=user,
                    notification_type=notification_type,
                    event_key=event_key,
                    title=title,
                    message=message,
                    data=data or {},
                    locale=cls._get_user_locale(user),
                    budget=budget,
                )

            return notification, True

        except IntegrityError:
            # Другой параллельный процесс мог создать это событие
            # между предварительной проверкой и INSERT.
            existing = Notification.objects.filter(
                user=user,
                event_key=event_key,
            ).first()

            if existing is not None:
                return existing, False

            # Если сработало другое ограничение уникальности,
            # например старое бюджетное, возвращаем его запись.
            if budget is not None:
                existing = Notification.objects.filter(
                    user=user,
                    budget=budget,
                    notification_type=notification_type,
                ).first()

                if existing is not None:
                    return existing, False

            # Не скрываем неожиданное нарушение целостности БД.
            raise
