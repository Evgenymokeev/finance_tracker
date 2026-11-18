from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase

from budgets.models import Budget
from categories.models import Category
from rest_framework import status
from rest_framework.test import APITestCase
from users.models import UserSettings

from .models import Notification
from .services import NotificationService


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
