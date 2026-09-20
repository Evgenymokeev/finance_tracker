from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    NotificationSettings,
    UserProfile,
    UserSettings,
)


class UserProfileAPITest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        self.client.force_authenticate(
            user=self.user
        )

    def test_get_profile(self):
        response = self.client.get(
            "/api/v1/auth/profile/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["username"],
            "testuser"
        )

        self.assertEqual(
            response.data["email"],
            "test@example.com"
        )

    def test_update_profile(self):
        data = {
            "first_name": "Evgeny",
            "last_name": "Mokeev",
            "email": "newemail@example.com"
        }

        response = self.client.patch(
            "/api/v1/auth/profile/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.user.refresh_from_db()

        self.assertEqual(
            self.user.first_name,
            "Evgeny"
        )

        self.assertEqual(
            self.user.last_name,
            "Mokeev"
        )

        self.assertEqual(
            self.user.email,
            "newemail@example.com"
        )

    def test_update_profile_with_existing_email(self):
        User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="testpass123"
        )

        data = {
            "email": "another@example.com"
        }

        response = self.client.patch(
            "/api/v1/auth/profile/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "email",
            response.data
        )

    def test_change_password(self):
        data = {
            "old_password": "testpass123",
            "new_password": "newpassword123"
        }

        response = self.client.post(
            "/api/v1/auth/change-password/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password(
                "newpassword123"
            )
        )

    def test_change_password_with_wrong_old_password(self):
        data = {
            "old_password": "wrongpassword",
            "new_password": "newpassword123"
        }

        response = self.client.post(
            "/api/v1/auth/change-password/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_change_password_with_short_password(self):
        data = {
            "old_password": "testpass123",
            "new_password": "1234567"
        }

        response = self.client.post(
            "/api/v1/auth/change-password/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_register(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpass123"
        }

        response = self.client.post(
            "/api/v1/auth/register/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertTrue(
            User.objects.filter(
                username="newuser"
            ).exists()
        )

        # При регистрации вместе с User должны автоматически
        # создаваться профиль, пользовательские настройки
        # и настройки уведомлений.
        user = User.objects.get(
            username="newuser"
        )

        self.assertTrue(
            UserProfile.objects.filter(
                user=user
            ).exists()
        )

        self.assertTrue(
            UserSettings.objects.filter(
                user=user
            ).exists()
        )

        self.assertTrue(
            NotificationSettings.objects.filter(
                user=user
            ).exists()
        )

    def test_register_creates_default_user_settings(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "username": "settingsuser",
            "email": "settings@example.com",
            "password": "newpass123"
        }

        response = self.client.post(
            "/api/v1/auth/register/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        user = User.objects.get(
            username="settingsuser"
        )

        # Проверяем настройки пользователя,
        # которые создаются автоматически при регистрации.
        user_settings = UserSettings.objects.get(
            user=user
        )

        self.assertEqual(
            user_settings.language,
            UserSettings.Language.ENGLISH
        )

        self.assertEqual(
            user_settings.currency,
            UserSettings.Currency.CZK
        )

        self.assertEqual(
            user_settings.timezone,
            "UTC"
        )

        # Проверяем настройки уведомлений по умолчанию.
        notification_settings = NotificationSettings.objects.get(
            user=user
        )

        self.assertTrue(
            notification_settings.email_enabled
        )

        self.assertTrue(
            notification_settings.push_enabled
        )

        self.assertFalse(
            notification_settings.telegram_enabled
        )

        self.assertTrue(
            notification_settings.daily_summary
        )

    def test_register_with_short_password(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "1234567"
        }

        response = self.client.post(
            "/api/v1/auth/register/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_register_with_existing_email(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "username": "anotheruser",
            "email": "test@example.com",
            "password": "newpass123"
        }

        response = self.client.post(
            "/api/v1/auth/register/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "email",
            response.data
        )

    def test_get_user_settings(self):
        response = self.client.get(
            "/api/v1/auth/settings/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["language"],
            "en"
        )

        self.assertEqual(
            response.data["currency"],
            "CZK"
        )

        self.assertEqual(
            response.data["timezone"],
            "UTC"
        )

    def test_update_user_settings(self):
        data = {
            "language": "ru",
            "currency": "EUR",
            "timezone": "Europe/Prague"
        }

        response = self.client.patch(
            "/api/v1/auth/settings/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["language"],
            "ru"
        )

        self.assertEqual(
            response.data["currency"],
            "EUR"
        )

        self.assertEqual(
            response.data["timezone"],
            "Europe/Prague"
        )

        # Проверяем, что изменения действительно записались в базу.
        self.user.refresh_from_db()

        user_settings = self.user.settings

        self.assertEqual(
            user_settings.language,
            "ru"
        )

        self.assertEqual(
            user_settings.currency,
            "EUR"
        )

        self.assertEqual(
            user_settings.timezone,
            "Europe/Prague"
        )

    def test_update_user_settings_with_invalid_currency(self):
        data = {
            "currency": "GBP"
        }

        response = self.client.patch(
            "/api/v1/auth/settings/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "currency",
            response.data
        )

    def test_update_user_settings_with_invalid_language(self):
        data = {
            "language": "de"
        }

        response = self.client.patch(
            "/api/v1/auth/settings/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "language",
            response.data
        )

    def test_get_notification_settings(self):
        response = self.client.get(
            "/api/v1/auth/notification-settings/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertTrue(
            response.data["email_enabled"]
        )

        self.assertTrue(
            response.data["push_enabled"]
        )

        self.assertFalse(
            response.data["telegram_enabled"]
        )

        self.assertTrue(
            response.data["daily_summary"]
        )


    def test_update_notification_settings(self):
        data = {
            "email_enabled": False,
            "push_enabled": False,
            "telegram_enabled": True,
            "daily_summary": False,
        }

        response = self.client.patch(
            "/api/v1/auth/notification-settings/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertFalse(
            response.data["email_enabled"]
        )

        self.assertFalse(
            response.data["push_enabled"]
        )

        self.assertTrue(
            response.data["telegram_enabled"]
        )

        self.assertFalse(
            response.data["daily_summary"]
        )

        # Проверяем, что изменения действительно записались в базу.
        self.user.refresh_from_db()

        notification_settings = self.user.notification_settings

        self.assertFalse(
            notification_settings.email_enabled
        )

        self.assertFalse(
            notification_settings.push_enabled
        )

        self.assertTrue(
            notification_settings.telegram_enabled
        )

        self.assertFalse(
            notification_settings.daily_summary
        )

    def test_get_user_settings_requires_authentication(self):
        self.client.force_authenticate(
            user=None
        )

        response = self.client.get(
            "/api/v1/auth/settings/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )


    def test_update_user_settings_requires_authentication(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "language": "ru",
            "currency": "EUR",
            "timezone": "Europe/Prague"
        }

        response = self.client.patch(
            "/api/v1/auth/settings/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )


    def test_get_notification_settings_requires_authentication(self):
        self.client.force_authenticate(
            user=None
        )

        response = self.client.get(
            "/api/v1/auth/notification-settings/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )


    def test_update_notification_settings_requires_authentication(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "email_enabled": False,
            "push_enabled": False,
            "telegram_enabled": True,
            "daily_summary": False,
        }

        response = self.client.patch(
            "/api/v1/auth/notification-settings/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_user_settings_are_isolated_between_users(self):
        # Создаём второго пользователя.
        another_user = User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="testpass123"
        )

        # Создаём для него отдельные настройки.
        another_settings = UserSettings.objects.create(
            user=another_user,
            language="ru",
            currency="EUR",
            timezone="Europe/Prague",
        )

        # Текущий пользователь должен получить только свои настройки.
        response = self.client.get(
            "/api/v1/auth/settings/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["language"],
            self.user.settings.language
        )

        self.assertEqual(
            response.data["currency"],
            self.user.settings.currency
        )

        # Проверяем, что настройки второго пользователя
        # не были возвращены.
        self.assertNotEqual(
            response.data["language"],
            another_settings.language
        )

        self.assertNotEqual(
            response.data["currency"],
            another_settings.currency
        )


    def test_notification_settings_are_isolated_between_users(self):
        # Создаём второго пользователя.
        another_user = User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="testpass123"
        )

        # Создаём для него отдельные настройки уведомлений.
        another_notification_settings = (
            NotificationSettings.objects.create(
                user=another_user,
                email_enabled=False,
                push_enabled=False,
                telegram_enabled=True,
                daily_summary=False,
            )
        )

        # Текущий пользователь должен получить только свои настройки.
        response = self.client.get(
            "/api/v1/auth/notification-settings/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        # Проверяем, что настройки текущего пользователя
        # отличаются от настроек второго пользователя.
        self.assertNotEqual(
            response.data["email_enabled"],
            another_notification_settings.email_enabled
        )

        self.assertNotEqual(
            response.data["push_enabled"],
            another_notification_settings.push_enabled
        )

        self.assertNotEqual(
            response.data["telegram_enabled"],
            another_notification_settings.telegram_enabled
        )

        self.assertNotEqual(
            response.data["daily_summary"],
            another_notification_settings.daily_summary
        )

# Create your tests here.
