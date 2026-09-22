from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.test import APITestCase

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
