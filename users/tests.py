from django.contrib.auth.models import User
from unittest.mock import patch
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import (
    Household,
    HouseholdMembership,
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

    def test_register_with_common_password(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "username": "commonuser",
            "email": "common@example.com",
            "password": "password"
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
            "password",
            response.data
        )

    def test_register_with_numeric_password(self):
        self.client.force_authenticate(
            user=None
        )

        data = {
            "username": "numericuser",
            "email": "numeric@example.com",
            "password": "123456789"
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
            "password",
            response.data
        )

    def test_change_password_with_common_password(self):
        data = {
            "old_password": "testpass123",
            "new_password": "password"
        }

        response = self.client.post(
            "/api/v1/auth/change-password/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "new_password",
            response.data
        )

    def test_change_password_with_numeric_password(self):
        data = {
            "old_password": "testpass123",
            "new_password": "123456789"
        }

        response = self.client.post(
            "/api/v1/auth/change-password/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "new_password",
            response.data
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

    def test_update_user_settings_with_valid_timezone(self):
        data = {
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
            response.data["timezone"],
            "Europe/Prague"
        )

        self.user.settings.refresh_from_db()

        self.assertEqual(
            self.user.settings.timezone,
            "Europe/Prague"
        )

    def test_update_user_settings_with_invalid_timezone(self):
        data = {
            "timezone": "Invalid/Timezone"
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
            "timezone",
            response.data
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

    def test_create_household(self):
        data = {
            "name": "My Family",
        }

        response = self.client.post(
            "/api/v1/auth/households/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        # Проверяем, что Household действительно создан.
        self.assertTrue(
            Household.objects.filter(
                name="My Family",
                created_by=self.user,
            ).exists()
        )

        household = Household.objects.get(
            name="My Family",
            created_by=self.user,
        )

        # Проверяем, что создатель автоматически получил
        # роль OWNER в HouseholdMembership.
        self.assertTrue(
            HouseholdMembership.objects.filter(
                household=household,
                user=self.user,
                role=HouseholdMembership.Role.OWNER,
            ).exists()
        )

        # Проверяем, что API возвращает основные данные Household.
        self.assertEqual(
            response.data["name"],
            "My Family"
        )

        self.assertEqual(
            response.data["created_by"],
            self.user.id
        )

    def test_create_household_without_name(self):
        data = {}

        response = self.client.post(
            "/api/v1/auth/households/",
            data,
            format="json",
        )

        # Название Household обязательно.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        # Household не должен создаваться при ошибке валидации.
        self.assertEqual(
            Household.objects.count(),
            0
        )

    def test_list_households(self):
        # Создаём Household через API.
        create_response = self.client.post(
            "/api/v1/auth/households/",
            {
                "name": "My Family",
            },
            format="json",
        )

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED
        )

        # Получаем список Household текущего пользователя.
        response = self.client.get(
            "/api/v1/auth/households/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        # DRF использует пагинацию, поэтому сами Household
        # находятся внутри поля "results".
        self.assertEqual(
            len(response.data["results"]),
            1
        )

        self.assertEqual(
            response.data["results"][0]["name"],
            "My Family"
        )

    def test_list_households_only_returns_user_households(self):
        # Создаём Household текущего пользователя.
        own_household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        HouseholdMembership.objects.create(
            household=own_household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём второго пользователя.
        another_user = User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="testpass123",
        )

        # Создаём Household второго пользователя.
        another_household = Household.objects.create(
            name="Another Family",
            created_by=another_user,
        )

        HouseholdMembership.objects.create(
            household=another_household,
            user=another_user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Получаем список Household текущего пользователя.
        response = self.client.get(
            "/api/v1/auth/households/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        results = response.data["results"]

        # Текущий пользователь должен видеть только
        # Household, в котором он состоит.
        self.assertEqual(
            len(results),
            1
        )

        self.assertEqual(
            results[0]["name"],
            "My Family"
        )

        # Household другого пользователя не должен попасть
        # в результат.
        self.assertNotIn(
            "Another Family",
            [household["name"] for household in results]
        )

    def test_retrieve_household(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Получаем конкретный Household.
        response = self.client.get(
            f"/api/v1/auth/households/{household.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        # Проверяем, что API возвращает правильный Household.
        self.assertEqual(
            response.data["id"],
            household.id
        )

        self.assertEqual(
            response.data["name"],
            "My Family"
        )

        self.assertEqual(
            response.data["created_by"],
            self.user.id
            )


    def test_retrieve_household_not_member_returns_404(self):
        # Создаём второго пользователя.
        another_user = User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="testpass123",
        )

        # Создаём Household второго пользователя.
        household = Household.objects.create(
            name="Another Family",
            created_by=another_user,
        )

        HouseholdMembership.objects.create(
            household=household,
            user=another_user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Текущий пользователь не является участником
        # этого Household.
        response = self.client.get(
            f"/api/v1/auth/households/{household.id}/"
        )

        # Объект не должен быть доступен через queryset
        # текущего пользователя.
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    def test_owner_can_update_household(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # OWNER должен иметь возможность изменить название Household.
        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/",
            {
                "name": "Updated Family",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        household.refresh_from_db()

        # Проверяем, что изменение действительно сохранилось.
        self.assertEqual(
            household.name,
            "Updated Family"
        )

    def test_adult_cannot_update_household(self):
        # Создаём Household.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Создаём второго пользователя с ролью ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Переключаем запрос на взрослого участника.
        self.client.force_authenticate(
            user=adult_user
        )

        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/",
            {
                "name": "Hacked Family",
            },
            format="json",
        )

        # ADULT не должен иметь право изменять Household.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        household.refresh_from_db()

        # Проверяем, что название осталось неизменным.
        self.assertEqual(
            household.name,
            "My Family"
        )

    def test_child_cannot_update_household(self):
        # Создаём Household.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Создаём второго пользователя с ролью CHILD.
        child_user = User.objects.create_user(
            username="childuser",
            email="child@example.com",
            password="testpass123",
        )

        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        HouseholdMembership.objects.create(
            household=household,
            user=child_user,
            role=HouseholdMembership.Role.CHILD,
        )

        # Переключаем запрос на ребёнка.
        self.client.force_authenticate(
            user=child_user
        )

        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/",
            {
                "name": "Hacked Family",
            },
            format="json",
        )

        # CHILD не должен иметь право изменять Household.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        household.refresh_from_db()

        # Проверяем, что название осталось неизменным.
        self.assertEqual(
            household.name,
            "My Family"
        )

    def test_owner_can_delete_household(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # OWNER должен иметь возможность удалить Household.
        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT
        )

        # Проверяем, что Household действительно удалён.
        self.assertFalse(
            Household.objects.filter(id=household.id).exists()
        )


    def test_adult_cannot_delete_household(self):
        # Создаём Household.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Создаём второго пользователя с ролью ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Переключаем запрос на взрослого участника.
        self.client.force_authenticate(
            user=adult_user
        )

        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/"
        )

        # ADULT не должен иметь право удалять Household.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        # Проверяем, что Household остался.
        self.assertTrue(
            Household.objects.filter(id=household.id).exists()
        )


    def test_child_cannot_delete_household(self):
        # Создаём Household.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Создаём второго пользователя с ролью CHILD.
        child_user = User.objects.create_user(
            username="childuser",
            email="child@example.com",
            password="testpass123",
        )

        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        HouseholdMembership.objects.create(
            household=household,
            user=child_user,
            role=HouseholdMembership.Role.CHILD,
        )

        # Переключаем запрос на ребёнка.
        self.client.force_authenticate(
            user=child_user
        )

        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/"
        )

        # CHILD не должен иметь право удалять Household.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        # Проверяем, что Household остался.
        self.assertTrue(
            Household.objects.filter(id=household.id).exists()
        )

    def test_owner_can_list_household_members(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя в Household
        # с ролью OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём второго пользователя с ролью ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Создаём третьего пользователя с ролью CHILD.
        child_user = User.objects.create_user(
            username="childuser",
            email="child@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в тот же Household.
        HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Добавляем CHILD в тот же Household.
        HouseholdMembership.objects.create(
            household=household,
            user=child_user,
            role=HouseholdMembership.Role.CHILD,
        )

        # OWNER запрашивает список участников Household.
        response = self.client.get(
            f"/api/v1/auth/households/{household.id}/members/"
        )

        # Проверяем, что запрос выполнен успешно.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Проверяем, что API вернуло общее количество
        # участников Household.
        self.assertEqual(
            response.data["count"],
            3,
        )

        # Получаем список участников из поля results,
        # которое содержит данные текущей страницы.
        members = response.data["results"]

        # Проверяем, что на текущей странице находятся
        # все три участника Household.
        self.assertEqual(
            len(members),
            3,
        )

        # Получаем usernames всех участников,
        # которые вернул API.
        usernames = {
            member["username"]
            for member in members
        }

        # Проверяем, что API вернуло именно этих участников.
        self.assertEqual(
            usernames,
            {
                "testuser",
                "adultuser",
                "childuser",
            },
        )

    def test_adult_can_list_household_members(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя в Household
        # с ролью OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём пользователя с ролью ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в Household.
        HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Переключаем запрос на пользователя с ролью ADULT.
        self.client.force_authenticate(
            user=adult_user
        )

        # ADULT запрашивает список участников Household.
        response = self.client.get(
            f"/api/v1/auth/households/{household.id}/members/"
        )

        # Проверяем, что ADULT может просматривать участников.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Проверяем, что API вернуло общее количество
        # участников Household.
        self.assertEqual(
            response.data["count"],
            2,
        )

        # Получаем участников из текущей страницы.
        members = response.data["results"]

        # Проверяем, что текущая страница содержит
        # OWNER и ADULT.
        self.assertEqual(
            len(members),
            2,
        )

    def test_non_member_cannot_list_household_members(self):
        # Создаём Household.
        household = Household.objects.create(
            name="Another Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя в Household
        # с ролью OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём пользователя, который не состоит
        # в данном Household.
        another_user = User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="testpass123",
        )

        # Переключаем запрос на пользователя,
        # который не является участником Household.
        self.client.force_authenticate(
            user=another_user
        )

        # Не участник пытается получить список участников.
        response = self.client.get(
            f"/api/v1/auth/households/{household.id}/members/"
        )

        # Проверяем, что доступ запрещён.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_list_household_members_requires_authentication(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя в Household
        # с ролью OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Убираем аутентификацию,
        # чтобы выполнить запрос от имени анонимного пользователя.
        self.client.force_authenticate(
            user=None
        )

        # Неавторизованный пользователь пытается
        # получить список участников Household.
        response = self.client.get(
            f"/api/v1/auth/households/{household.id}/members/"
        )

        # Проверяем, что API требует авторизацию.
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_owner_can_add_adult_member(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя в Household
        # с ролью OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём пользователя, которого OWNER будет добавлять.
        new_user = User.objects.create_user(
            username="newadult",
            email="newadult@example.com",
            password="testpass123",
        )

        # OWNER добавляет нового пользователя с ролью ADULT.
        response = self.client.post(
            f"/api/v1/auth/households/{household.id}/members/",
            {
                "user": new_user.id,
                "role": HouseholdMembership.Role.ADULT,
            },
            format="json",
        )

        # Проверяем успешное создание участника.
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        # Проверяем, что membership действительно создана.
        membership = HouseholdMembership.objects.get(
            household=household,
            user=new_user,
        )

        # Проверяем правильную роль нового участника.
        self.assertEqual(
            membership.role,
            HouseholdMembership.Role.ADULT,
        )

        # Проверяем, что API вернул правильного пользователя.
        self.assertEqual(
            response.data["user"],
            new_user.id,
        )

        # Проверяем username нового участника в ответе API.
        self.assertEqual(
            response.data["username"],
            "newadult",
        )

    def test_owner_can_add_child_member(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя с ролью OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём пользователя, которого будем добавлять.
        new_user = User.objects.create_user(
            username="newchild",
            email="newchild@example.com",
            password="testpass123",
        )

        # OWNER добавляет пользователя с ролью CHILD.
        response = self.client.post(
            f"/api/v1/auth/households/{household.id}/members/",
            {
                "user": new_user.id,
                "role": HouseholdMembership.Role.CHILD,
            },
            format="json",
        )

        # Проверяем успешное создание участника.
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        # Получаем созданную membership из базы.
        membership = HouseholdMembership.objects.get(
            household=household,
            user=new_user,
        )

        # Проверяем правильную роль.
        self.assertEqual(
            membership.role,
            HouseholdMembership.Role.CHILD,
        )

    def test_adult_cannot_add_member(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём пользователя с ролью ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Создаём пользователя, которого ADULT попытается добавить.
        new_user = User.objects.create_user(
            username="newmember",
            email="newmember@example.com",
            password="testpass123",
        )

        # Переключаем запрос на ADULT.
        self.client.force_authenticate(
            user=adult_user,
        )

        response = self.client.post(
            f"/api/v1/auth/households/{household.id}/members/",
            {
                "user": new_user.id,
                "role": HouseholdMembership.Role.ADULT,
            },
            format="json",
        )

        # ADULT не имеет права добавлять участников.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_child_cannot_add_member(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём пользователя с ролью CHILD.
        child_user = User.objects.create_user(
            username="childuser",
            email="child@example.com",
            password="testpass123",
        )

        HouseholdMembership.objects.create(
            household=household,
            user=child_user,
            role=HouseholdMembership.Role.CHILD,
        )

        # Создаём пользователя, которого CHILD попытается добавить.
        new_user = User.objects.create_user(
            username="newmember",
            email="newmember@example.com",
            password="testpass123",
        )

        # Переключаем запрос на CHILD.
        self.client.force_authenticate(
            user=child_user,
        )

        response = self.client.post(
            f"/api/v1/auth/households/{household.id}/members/",
            {
                "user": new_user.id,
                "role": HouseholdMembership.Role.ADULT,
            },
            format="json",
        )

        # CHILD не имеет права добавлять участников.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_member_cannot_add_member(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём пользователя, который не является
        # участником этого Household.
        outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="testpass123",
        )

        # Создаём пользователя, которого outsider
        # попытается добавить.
        new_user = User.objects.create_user(
            username="newmember",
            email="newmember@example.com",
            password="testpass123",
        )

        # Переключаем запрос на пользователя,
        # который не является участником Household.
        self.client.force_authenticate(
            user=outsider,
        )

        response = self.client.post(
            f"/api/v1/auth/households/{household.id}/members/",
            {
                "user": new_user.id,
                "role": HouseholdMembership.Role.ADULT,
            },
            format="json",
        )

        # Неучастник не может добавлять участников.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_cannot_add_member(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём пользователя, которого можно было бы добавить.
        new_user = User.objects.create_user(
            username="newmember",
            email="newmember@example.com",
            password="testpass123",
        )

        # Убираем аутентификацию.
        self.client.force_authenticate(user=None)

        response = self.client.post(
            f"/api/v1/auth/households/{household.id}/members/",
            {
                "user": new_user.id,
                "role": HouseholdMembership.Role.ADULT,
            },
            format="json",
        )

        # Неавторизованный пользователь получает 401.
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_owner_cannot_add_existing_member(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в Household.
        HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # OWNER пытается повторно добавить того же пользователя.
        response = self.client.post(
            f"/api/v1/auth/households/{household.id}/members/",
            {
                "user": adult_user.id,
                "role": HouseholdMembership.Role.ADULT,
            },
            format="json",
        )

        # Повторное добавление запрещено.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Проверяем, что ошибка относится к полю user.
        self.assertIn(
            "user",
            response.data,
        )

    def test_owner_cannot_add_another_owner(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как единственного OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём нового пользователя.
        new_user = User.objects.create_user(
            username="secondowner",
            email="secondowner@example.com",
            password="testpass123",
        )

        # OWNER пытается добавить второго OWNER.
        response = self.client.post(
            f"/api/v1/auth/households/{household.id}/members/",
            {
                "user": new_user.id,
                "role": HouseholdMembership.Role.OWNER,
            },
            format="json",
        )

        # Второго OWNER нельзя создать через обычное добавление.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Проверяем, что ошибка относится к полю role.
        self.assertIn(
            "role",
            response.data,
        )

    def test_owner_can_change_adult_to_child(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в Household.
        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # OWNER изменяет роль ADULT на CHILD.
        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{adult_membership.id}/",
            {
                "role": HouseholdMembership.Role.CHILD,
            },
            format="json",
        )

        # Изменение роли должно быть успешным.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Проверяем, что роль действительно изменилась в базе данных.
        adult_membership.refresh_from_db()

        self.assertEqual(
            adult_membership.role,
            HouseholdMembership.Role.CHILD,
        )

        # Проверяем роль в ответе API.
        self.assertEqual(
            response.data["role"],
            HouseholdMembership.Role.CHILD,
        )

    def test_owner_can_change_child_to_adult(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём CHILD.
        child_user = User.objects.create_user(
            username="childuser",
            email="child@example.com",
            password="testpass123",
        )

        # Добавляем CHILD в Household.
        child_membership = HouseholdMembership.objects.create(
            household=household,
            user=child_user,
            role=HouseholdMembership.Role.CHILD,
        )

        # OWNER изменяет роль CHILD на ADULT.
        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{child_membership.id}/",
            {
                "role": HouseholdMembership.Role.ADULT,
            },
            format="json",
        )

        # Изменение роли должно быть успешным.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Проверяем, что роль действительно изменилась в базе данных.
        child_membership.refresh_from_db()

        self.assertEqual(
            child_membership.role,
            HouseholdMembership.Role.ADULT,
        )

        # Проверяем роль в ответе API.
        self.assertEqual(
            response.data["role"],
            HouseholdMembership.Role.ADULT,
        )

    def test_owner_cannot_change_own_role(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        owner_membership = HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # OWNER пытается изменить собственную роль на ADULT.
        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{owner_membership.id}/",
            {
                "role": HouseholdMembership.Role.ADULT,
            },
            format="json",
        )

        # Изменение собственной роли запрещено.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Проверяем, что ошибка относится к полю role.
        self.assertIn(
            "role",
            response.data,
        )

        # Проверяем, что роль OWNER не изменилась в базе данных.
        owner_membership.refresh_from_db()

        self.assertEqual(
            owner_membership.role,
            HouseholdMembership.Role.OWNER,
        )

    def test_owner_cannot_assign_another_owner(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём обычного участника.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Добавляем пользователя как ADULT.
        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # OWNER пытается назначить ADULT вторым OWNER.
        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{adult_membership.id}/",
            {
                "role": HouseholdMembership.Role.OWNER,
            },
            format="json",
        )

        # Назначение второго OWNER запрещено.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Проверяем, что ошибка относится к полю role.
        self.assertIn(
            "role",
            response.data,
        )

        # Проверяем, что исходная роль участника
        # не изменилась в базе данных.
        adult_membership.refresh_from_db()

        self.assertEqual(
            adult_membership.role,
            HouseholdMembership.Role.ADULT,
        )

    def test_adult_cannot_change_member_role(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём ADULT, который будет выполнять PATCH.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в Household.
        HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Создаём CHILD, роль которого ADULT попытается изменить.
        child_user = User.objects.create_user(
            username="childuser",
            email="child@example.com",
            password="testpass123",
        )

        # Добавляем CHILD в Household.
        child_membership = HouseholdMembership.objects.create(
            household=household,
            user=child_user,
            role=HouseholdMembership.Role.CHILD,
        )

        # Переключаем авторизацию на ADULT.
        self.client.force_authenticate(
            user=adult_user,
        )

        # ADULT пытается изменить роль CHILD.
        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{child_membership.id}/",
            {
                "role": HouseholdMembership.Role.ADULT,
            },
            format="json",
        )

        # ADULT не имеет права изменять роли участников.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Проверяем, что роль CHILD не изменилась.
        child_membership.refresh_from_db()

        self.assertEqual(
            child_membership.role,
            HouseholdMembership.Role.CHILD,
        )

    def test_child_cannot_change_member_role(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём CHILD, который будет выполнять PATCH.
        child_user = User.objects.create_user(
            username="childuser",
            email="child@example.com",
            password="testpass123",
        )

        # Добавляем CHILD в Household.
        HouseholdMembership.objects.create(
            household=household,
            user=child_user,
            role=HouseholdMembership.Role.CHILD,
        )

        # Создаём ADULT, роль которого CHILD попытается изменить.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в Household.
        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Переключаем авторизацию на CHILD.
        self.client.force_authenticate(
            user=child_user,
        )

        # CHILD пытается изменить роль ADULT.
        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{adult_membership.id}/",
            {
                "role": HouseholdMembership.Role.CHILD,
            },
            format="json",
        )

        # CHILD не имеет права изменять роли участников.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Проверяем, что роль ADULT не изменилась.
        adult_membership.refresh_from_db()

        self.assertEqual(
            adult_membership.role,
            HouseholdMembership.Role.ADULT,
        )

    def test_non_member_cannot_change_member_role(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём ADULT, роль которого будет изменяться.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в Household.
        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Создаём пользователя, который НЕ является
        # участником этого Household.
        outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="testpass123",
        )

        # Переключаем авторизацию на неучастника.
        self.client.force_authenticate(
            user=outsider,
        )

        # Неучастник пытается изменить роль ADULT.
        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{adult_membership.id}/",
            {
                "role": HouseholdMembership.Role.CHILD,
            },
            format="json",
        )

        # Неучастник не имеет права изменять роли участников.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Проверяем, что роль ADULT не изменилась.
        adult_membership.refresh_from_db()

        self.assertEqual(
            adult_membership.role,
            HouseholdMembership.Role.ADULT,
        )

    def test_unauthenticated_cannot_change_member_role(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём ADULT, роль которого будем изменять.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в Household.
        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Убираем аутентификацию.
        self.client.force_authenticate(user=None)

        # Неавторизованный пользователь пытается изменить роль ADULT.
        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{adult_membership.id}/",
            {
                "role": HouseholdMembership.Role.CHILD,
            },
            format="json",
        )

        # Неавторизованный пользователь получает 401.
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        # Проверяем, что роль ADULT не изменилась.
        adult_membership.refresh_from_db()

        self.assertEqual(
            adult_membership.role,
            HouseholdMembership.Role.ADULT,
        )

    def test_owner_cannot_change_member_user(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Создаём другого пользователя.
        another_user = User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в Household.
        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # OWNER пытается изменить не только роль,
        # но и пользователя, связанного с membership.
        response = self.client.patch(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{adult_membership.id}/",
            {
                "user": another_user.id,
                "role": HouseholdMembership.Role.CHILD,
            },
            format="json",
        )

        # Передача поля user должна быть запрещена.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Проверяем, что ошибка относится к полю user.
        self.assertIn(
            "user",
            response.data,
        )

        # Проверяем, что пользователь membership не изменился.
        adult_membership.refresh_from_db()

        self.assertEqual(
            adult_membership.user,
            adult_user,
        )

        # Проверяем, что роль тоже не изменилась.
        self.assertEqual(
            adult_membership.role,
            HouseholdMembership.Role.ADULT,
        )

    def test_owner_can_delete_adult_member(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в Household.
        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # OWNER удаляет ADULT.
        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{adult_membership.id}/",
        )

        # Удаление успешно выполнено.
        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        # Проверяем, что membership действительно удалён.
        self.assertFalse(
            HouseholdMembership.objects.filter(
                id=adult_membership.id,
            ).exists()
        )

    def test_owner_can_delete_child_member(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём CHILD.
        child_user = User.objects.create_user(
            username="childuser",
            email="child@example.com",
            password="testpass123",
        )

        # Добавляем CHILD в Household.
        child_membership = HouseholdMembership.objects.create(
            household=household,
            user=child_user,
            role=HouseholdMembership.Role.CHILD,
        )

        # OWNER удаляет CHILD.
        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{child_membership.id}/",
        )

        # Удаление успешно выполнено.
        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        # Проверяем, что membership действительно удалён.
        self.assertFalse(
            HouseholdMembership.objects.filter(
                id=child_membership.id,
            ).exists()
        )

    def test_owner_cannot_delete_themselves(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        owner_membership = HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # OWNER пытается удалить самого себя.
        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{owner_membership.id}/",
        )

        # Удаление самого себя запрещено.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Проверяем, что OWNER остался в Household.
        self.assertTrue(
            HouseholdMembership.objects.filter(
                id=owner_membership.id,
            ).exists()
        )

    def test_household_cannot_have_two_owners(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём другого пользователя.
        another_owner = User.objects.create_user(
            username="anotherowner",
            email="anotherowner@example.com",
            password="testpass123",
        )

        # Попытка создать второго OWNER должна быть запрещена
        # ограничением unique_household_owner на уровне БД.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                HouseholdMembership.objects.create(
                    household=household,
                    user=another_owner,
                    role=HouseholdMembership.Role.OWNER,
                )

        # Проверяем, что OWNER в Household по-прежнему только один.
        self.assertEqual(
            HouseholdMembership.objects.filter(
                household=household,
                role=HouseholdMembership.Role.OWNER,
            ).count(),
            1,
        )

    def test_adult_cannot_delete_member(self):
        # Создаём Household.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Создаём OWNER.
        owner_user = User.objects.create_user(
            username="owneruser",
            email="owner@example.com",
            password="testpass123",
        )

        # Добавляем OWNER в Household.
        HouseholdMembership.objects.create(
            household=household,
            user=owner_user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        # Добавляем ADULT в Household.
        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Создаём CHILD, которого ADULT попытается удалить.
        child_user = User.objects.create_user(
            username="childuser",
            email="child@example.com",
            password="testpass123",
        )

        child_membership = HouseholdMembership.objects.create(
            household=household,
            user=child_user,
            role=HouseholdMembership.Role.CHILD,
        )

        # Авторизуемся как ADULT.
        self.client.force_authenticate(user=adult_user)

        # ADULT пытается удалить CHILD.
        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{child_membership.id}/",
        )

        # ADULT не имеет права удалять участников.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Проверяем, что CHILD остался в Household.
        self.assertTrue(
            HouseholdMembership.objects.filter(
                id=child_membership.id,
            ).exists()
        )

    def test_child_cannot_delete_member(self):
        # Создаём Household.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Создаём OWNER.
        owner_user = User.objects.create_user(
            username="owneruser",
            email="owner@example.com",
            password="testpass123",
        )

        # Добавляем OWNER в Household.
        HouseholdMembership.objects.create(
            household=household,
            user=owner_user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём CHILD.
        child_user = User.objects.create_user(
            username="childuser",
            email="child@example.com",
            password="testpass123",
        )

        # Добавляем CHILD в Household.
        HouseholdMembership.objects.create(
            household=household,
            user=child_user,
            role=HouseholdMembership.Role.CHILD,
        )

        # Создаём ADULT, которого CHILD попытается удалить.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Авторизуемся как CHILD.
        self.client.force_authenticate(user=child_user)

        # CHILD пытается удалить ADULT.
        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{adult_membership.id}/",
        )

        # CHILD не имеет права удалять участников.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Проверяем, что ADULT остался в Household.
        self.assertTrue(
            HouseholdMembership.objects.filter(
                id=adult_membership.id,
            ).exists()
        )

    def test_non_member_cannot_delete_household_member(self):
        # Создаём Household.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Создаём пользователя, который не состоит в Household.
        outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="testpass123",
        )

        # Авторизуемся как пользователь вне Household.
        self.client.force_authenticate(user=outsider)

        # Outsider пытается удалить ADULT.
        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{adult_membership.id}/",
        )

        # Пользователь вне Household не имеет права удалять участников.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Проверяем, что ADULT остался.
        self.assertTrue(
            HouseholdMembership.objects.filter(
                id=adult_membership.id,
            ).exists()
        )

    def test_unauthenticated_cannot_delete_member(self):
        # Создаём Household текущего пользователя.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём ADULT.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        adult_membership = HouseholdMembership.objects.create(
            household=household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # Убираем аутентификацию.
        self.client.force_authenticate(user=None)

        # Неавторизованный пользователь пытается удалить ADULT.
        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{adult_membership.id}/",
        )

        # Неавторизованный пользователь получает 401.
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        # Проверяем, что ADULT не был удалён.
        self.assertTrue(
            HouseholdMembership.objects.filter(
                id=adult_membership.id,
            ).exists()
        )

    def test_owner_cannot_delete_member_from_another_household(self):
        # Создаём первый Household.
        household = Household.objects.create(
            name="My Family",
            created_by=self.user,
        )

        # Добавляем текущего пользователя как OWNER первого Household.
        HouseholdMembership.objects.create(
            household=household,
            user=self.user,
            role=HouseholdMembership.Role.OWNER,
        )

        # Создаём второй Household.
        another_household = Household.objects.create(
            name="Another Family",
            created_by=self.user,
        )

        # Создаём участника второго Household.
        adult_user = User.objects.create_user(
            username="adultuser",
            email="adult@example.com",
            password="testpass123",
        )

        another_membership = HouseholdMembership.objects.create(
            household=another_household,
            user=adult_user,
            role=HouseholdMembership.Role.ADULT,
        )

        # OWNER первого Household пытается удалить
        # участника второго Household.
        response = self.client.delete(
            f"/api/v1/auth/households/{household.id}/members/"
            f"{another_membership.id}/",
        )

        # Участник не найден внутри первого Household,
        # поэтому возвращается 404.
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # Проверяем, что участник второго Household не удалён.
        self.assertTrue(
            HouseholdMembership.objects.filter(
                id=another_membership.id,
            ).exists()
        )

    @patch("users.views.send_mail")
    def test_password_reset_request_existing_email(self, mock_send_mail):
        # Отключаем авторизацию.
        # Password Reset должен быть доступен пользователю,
        # который не может войти в аккаунт.
        self.client.force_authenticate(user=None)

        # Отправляем запрос на восстановление пароля
        # для существующего пользователя.
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "test@example.com"},
        )

        # Запрос должен успешно обработаться.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Проверяем текст ответа.
        #
        # Он специально одинаковый для существующего
        # и несуществующего email.
        # Это не позволяет определить,
        # зарегистрирован ли такой пользователь.
        self.assertEqual(
            response.data["detail"],
            (
                "If an account with this email exists, "
                "a password reset link has been sent."
            ),
        )

        # Для существующего пользователя письмо
        # действительно должно быть отправлено.
        mock_send_mail.assert_called_once()

        # Проверяем, что письмо отправляется
        # именно на email пользователя.
        self.assertEqual(
            mock_send_mail.call_args.kwargs["recipient_list"],
            ["test@example.com"],
        )

    @patch("users.views.send_mail")
    def test_password_reset_request_unknown_email(self, mock_send_mail):
        # Отключаем авторизацию.
        # Восстановление пароля не требует JWT.
        self.client.force_authenticate(user=None)

        # Отправляем email, которого нет в базе данных.
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "unknown@example.com"},
        )

        # API всё равно возвращает 200.
        #
        # Мы не должны сообщать клиенту:
        # "Такого пользователя нет".
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Ответ должен быть таким же,
        # как и для существующего пользователя.
        self.assertEqual(
            response.data["detail"],
            (
                "If an account with this email exists, "
                "a password reset link has been sent."
            ),
        )

        # Но письмо отправляться не должно,
        # потому что такого пользователя нет.
        mock_send_mail.assert_not_called()

    @patch("users.views.send_mail")
    def test_password_reset_request_invalid_email(self, mock_send_mail):
        # Отключаем авторизацию.
        self.client.force_authenticate(user=None)

        # Передаём строку, которая не является корректным email.
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "not-an-email"},
        )

        # Serializer должен отклонить неправильный формат email.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Письмо в этом случае отправляться не должно,
        # потому что запрос не прошёл валидацию.
        mock_send_mail.assert_not_called()

    @patch("users.views.send_mail")
    def test_password_reset_request_does_not_require_authentication(
        self,
        mock_send_mail,
    ):
        # Пользователь не авторизован.
        self.client.force_authenticate(user=None)

        # Но он всё равно может запросить восстановление пароля.
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "test@example.com"},
        )

        # Запрос должен успешно обработаться.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_password_reset_confirm(self):
        # Получаем UID пользователя в том же формате,
        # который используется PasswordResetRequestView.
        uid = urlsafe_base64_encode(
            force_bytes(self.user.pk)
        )

        # Создаём настоящий Django password reset token
        # для нашего пользователя.
        #
        # Используем именно default_token_generator,
        # потому что его проверяет PasswordResetConfirmView.
        token = default_token_generator.make_token(
            self.user
        )

        # Запоминаем старый пароль.
        old_password = "testpass123"

        # Новый пароль должен соответствовать
        # настроенным Django password validators.
        new_password = "NewSecurePassword123!"

        # Password Reset должен работать без авторизации.
        self.client.force_authenticate(user=None)

        # Отправляем uid, token и новый пароль
        # на endpoint подтверждения сброса.
        response = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {
                "uid": uid,
                "token": token,
                "new_password": new_password,
            },
        )

        # Сброс пароля должен завершиться успешно.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Проверяем сообщение API.
        self.assertEqual(
            response.data["detail"],
            "Password has been reset successfully.",
        )

        # Обновляем объект пользователя из базы данных,
        # чтобы проверить именно сохранённый пароль.
        self.user.refresh_from_db()

        # Старый пароль больше не должен работать.
        self.assertFalse(
            self.user.check_password(old_password)
        )

        # Новый пароль должен работать.
        self.assertTrue(
            self.user.check_password(new_password)
        )

    def test_password_reset_confirm_invalid_token(self):
        # Получаем корректный UID существующего пользователя.
        uid = urlsafe_base64_encode(
            force_bytes(self.user.pk)
        )

        # Используем заведомо неправильный token.
        invalid_token = "invalid-token"

        # Запоминаем текущий пароль,
        # чтобы после запроса убедиться,
        # что он не был изменён.
        old_password = "testpass123"

        # Password Reset должен быть доступен
        # без авторизации.
        self.client.force_authenticate(user=None)

        # Отправляем запрос с неправильным token.
        response = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {
                "uid": uid,
                "token": invalid_token,
                "new_password": "NewSecurePassword123!",
            },
        )

        # Неправильный token должен привести к ошибке.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Проверяем сообщение об ошибочной ссылке.
        self.assertEqual(
            response.data["detail"],
            "Invalid password reset link.",
        )

        # Обновляем пользователя из базы данных.
        self.user.refresh_from_db()

        # Проверяем, что старый пароль всё ещё работает.
        self.assertTrue(
            self.user.check_password(old_password)
        )

    def test_password_reset_confirm_invalid_uid(self):
        # Используем строку, которая не является
        # корректным UID пользователя.
        invalid_uid = "invalid-uid"

        # Создаём настоящий token не имеет смысла,
        # потому что UID уже недействителен.
        token = default_token_generator.make_token(
            self.user
        )

        # Password Reset доступен без авторизации.
        self.client.force_authenticate(user=None)

        # Отправляем запрос с неправильным UID.
        response = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {
                "uid": invalid_uid,
                "token": token,
                "new_password": "NewSecurePassword123!",
            },
        )

        # Недействительный UID должен привести к ошибке.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Проверяем одинаковое безопасное сообщение.
        self.assertEqual(
            response.data["detail"],
            "Invalid password reset link.",
        )

        # Убеждаемся, что пароль пользователя
        # не был изменён.
        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password("testpass123")
        )

    def test_password_reset_confirm_weak_password(self):
        # Получаем корректный UID пользователя.
        uid = urlsafe_base64_encode(
            force_bytes(self.user.pk)
        )

        # Создаём настоящий token.
        token = default_token_generator.make_token(
            self.user
        )

        # Password Reset доступен без авторизации.
        self.client.force_authenticate(user=None)

        # Передаём слишком простой пароль.
        #
        # "12345678" соответствует минимальной длине,
        # но должен быть отклонён Django password validators.
        response = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {
                "uid": uid,
                "token": token,
                "new_password": "12345678",
            },
        )

        # Serializer должен отклонить пароль.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Проверяем, что ошибка относится именно
        # к new_password.
        self.assertIn(
            "new_password",
            response.data,
        )

        # Пароль пользователя не должен измениться.
        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password("testpass123")
        )

    def test_password_reset_confirm_token_cannot_be_reused(self):
        # Получаем корректный UID пользователя.
        uid = urlsafe_base64_encode(
            force_bytes(self.user.pk)
        )

        # Создаём настоящий Django password reset token.
        #
        # Этот token должен быть действительным
        # для первого запроса на смену пароля.
        token = default_token_generator.make_token(
            self.user
        )

        # Password Reset должен работать без авторизации.
        self.client.force_authenticate(user=None)

        # Первый запрос должен успешно изменить пароль.
        response = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {
                "uid": uid,
                "token": token,
                "new_password": "NewSecurePassword123!",
            },
        )

        # Первый сброс пароля должен завершиться успешно.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Обновляем пользователя из базы данных,
        # чтобы изменения пароля были учтены
        # при следующей проверке token.
        self.user.refresh_from_db()

        # Повторно используем тот же самый token.
        #
        # После изменения пароля Django должен
        # автоматически считать старый token недействительным.
        response = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {
                "uid": uid,
                "token": token,
                "new_password": "AnotherSecurePassword123!",
            },
        )

        # Повторное использование token должно быть запрещено.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Проверяем безопасное общее сообщение.
        self.assertEqual(
            response.data["detail"],
            "Invalid password reset link.",
        )

        # Проверяем, что второй пароль НЕ был установлен.
        self.assertTrue(
            self.user.check_password(
                "NewSecurePassword123!"
            )
        )

        self.assertFalse(
            self.user.check_password(
                "AnotherSecurePassword123!"
            )
        )

    def test_create_household_with_currency(self):
        # Создаём Household через API и явно указываем EUR.
        #
        # Это проверяет полный путь:
        # API → serializer → view → model → database.
        response = self.client.post(
            "/api/v1/auth/households/",
            {
                "name": "Family Budget",
                "currency": "EUR",
            },
            format="json",
        )

        # Household должен быть успешно создан.
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        # API должен вернуть ту валюту,
        # которую мы указали при создании.
        self.assertEqual(
            response.data["currency"],
            "EUR",
        )

        # Получаем Household непосредственно из базы.
        # Это дополнительно проверяет фактическое сохранение currency.
        household = Household.objects.get(
            id=response.data["id"]
        )

        # Убеждаемся, что в базе действительно сохранено EUR.
        self.assertEqual(
            household.currency,
            "EUR",
        )

    def test_create_household_uses_default_currency(self):
        # Создаём Household без указания currency.
        #
        # Это важно для обратной совместимости:
        # старый клиент API может пока не передавать новое поле.
        response = self.client.post(
            "/api/v1/auth/households/",
            {
                "name": "Family Budget",
            },
            format="json",
        )

        # Household должен успешно создаться.
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        # Если currency не передана,
        # модель должна использовать значение по умолчанию — CZK.
        self.assertEqual(
            response.data["currency"],
            "CZK",
        )

        # Проверяем фактическое значение в базе данных.
        household = Household.objects.get(
            id=response.data["id"]
        )

        # Убеждаемся, что default действительно сохранился.
        self.assertEqual(
            household.currency,
            "CZK",
        )

    def test_create_household_with_invalid_currency(self):
        # Пытаемся создать Household с валютой GBP.
        #
        # Сейчас GBP отсутствует среди разрешённых
        # валют UserSettings.Currency.
        response = self.client.post(
            "/api/v1/auth/households/",
            {
                "name": "Family Budget",
                "currency": "GBP",
            },
            format="json",
        )

        # Serializer должен отклонить неизвестную валюту.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Ошибка должна относиться именно к currency.
        self.assertIn(
            "currency",
            response.data,
        )

        # Household не должен быть создан.
        #
        # Здесь предполагается, что до этого теста
        # в БД нет других Household, созданных самим тестом.
        self.assertEqual(
            Household.objects.count(),
            0,
        )

    def test_update_household_currency(self):
        # Сначала создаём Household с валютой CZK.
        #
        # Это исходное состояние, которое затем будем изменять.
        response = self.client.post(
            "/api/v1/auth/households/",
            {
                "name": "Family Budget",
                "currency": "CZK",
            },
            format="json",
        )

        # Household должен быть создан.
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        household_id = response.data["id"]

        # Изменяем валюту Household с CZK на EUR.
        #
        # Используем PATCH, потому что меняем только одно поле,
        # а остальные данные Household должны остаться без изменений.
        response = self.client.patch(
            f"/api/v1/auth/households/{household_id}/",
            {
                "currency": "EUR",
            },
            format="json",
        )

        # OWNER должен иметь право изменить валюту Household.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    # API должен вернуть новую валюту.
        self.assertEqual(
            response.data["currency"],
            "EUR",
        )

    # Дополнительно проверяем значение непосредственно в БД.
        household = Household.objects.get(
            id=household_id
        )

        # Убеждаемся, что изменение действительно сохранилось.
        self.assertEqual(
            household.currency,
            "EUR",
        )
