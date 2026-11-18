"""
Сервис создания уведомлений.

Централизует создание событий, обеспечивает идемпотентность
по event_key и сохраняет язык и контекст уведомления
на момент его создания.
"""

from django.db import IntegrityError, transaction

from users.models import UserSettings

from .models import Notification


class NotificationService:
    """
    Единая точка создания уведомлений для приложений проекта.

    Сервис отвечает за сохранение события в базе данных.
    Отправка по внешним каналам выполняется отдельным механизмом.
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

        event_key идентифицирует конкретное бизнес-событие.
        Повторная обработка одного события (например, Celery-задачей)
        не создаёт дубликат.

        Разные event_key могут создавать отдельные уведомления,
        даже если они относятся к одному пользователю и бюджету.

        Уникальность event_key на уровне пользователя дополнительно
        защищается ограничением БД от конкурентных INSERT.

        Возвращает:
            (notification, created)
        """
        if not event_key:
            raise ValueError("event_key must not be empty")

        # Быстрый путь: событие уже было сохранено ранее.
        existing = Notification.objects.filter(
            user=user,
            event_key=event_key,
        ).first()

        if existing is not None:
            return existing, False

        try:
            # Отдельный atomic-блок создаёт savepoint, если вызывающий
            # код уже находится внутри транзакции.
            #
            # При IntegrityError этот блок откатывается до savepoint,
            # поэтому повторный SELECT можно безопасно выполнить
            # после выхода из atomic.
            with transaction.atomic():
                notification = Notification.objects.create(
                    user=user,
                    notification_type=notification_type,
                    event_key=event_key,
                    title=title,
                    message=message,
                    data=data if data is not None else {},
                    locale=cls._get_user_locale(user),
                    budget=budget,
                )

            return notification, True

        except IntegrityError:
            # Другой процесс мог одновременно создать событие
            # с тем же user + event_key.
            #
            # Уникальное ограничение БД гарантирует, что дубликат
            # не будет сохранён. После отката savepoint читаем
            # уже существующую запись.
            existing = Notification.objects.filter(
                user=user,
                event_key=event_key,
            ).first()

            if existing is not None:
                return existing, False

            # Если нарушение целостности вызвано другой причиной,
            # не маскируем ошибку и передаём её выше.
            raise
