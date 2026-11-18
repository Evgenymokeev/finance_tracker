from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

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

    def test_notification_not_duplicated(self):
        Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            title="Budget exceeded",
            message="You have exceeded your budget for Еда.",
            budget=self.budget,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Notification.objects.create(
                    user=self.user,
                    notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
                    title="Budget exceeded again",
                    message="You have exceeded your budget for Еда again.",
                    budget=self.budget,
                )

        self.assertEqual(
            Notification.objects.count(),
            1,
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

    def test_legacy_budget_notification_is_reused(self):
        """
        Старое бюджетное уведомление переиспользуется,
        а не заменяется новой записью.
        """
        legacy_notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            title="Old budget notification",
            message="Old notification message.",
            budget=self.budget,
        )

        notification, created = NotificationService.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
            event_key=f"budget:{self.budget.id}:budget_exceeded",
            title="Budget exceeded",
            message="New notification message.",
            budget=self.budget,
        )

        legacy_notification.refresh_from_db()

        self.assertFalse(created)
        self.assertEqual(notification.id, legacy_notification.id)
        self.assertEqual(
            legacy_notification.event_key,
            f"budget:{self.budget.id}:budget_exceeded",
        )
        self.assertEqual(Notification.objects.count(), 1)
