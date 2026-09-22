from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    RegisterView,
    LoginView,
    RefreshView,
    ProfileView,
    ChangePasswordView,
    UserSettingsView,
    NotificationSettingsView,
    HouseholdViewSet,
    HouseholdMembersView,
    HouseholdMemberDetailView,
)


urlpatterns = [
    # Регистрируем нового пользователя.
    path(
        "register/",
        RegisterView.as_view(),
        name="register",
    ),

    # Выполняем вход пользователя и получаем JWT-токены.
    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),

    # Обновляем access-токен с помощью refresh-токена.
    path(
        "token/refresh/",
        RefreshView.as_view(),
        name="refresh",
    ),

    # Получаем или изменяем профиль текущего пользователя.
    path(
        "profile/",
        ProfileView.as_view(),
        name="profile",
    ),

    # Получаем или изменяем настройки текущего пользователя.
    path(
        "settings/",
        UserSettingsView.as_view(),
        name="user-settings",
    ),

    # Получаем или изменяем настройки уведомлений текущего пользователя.
    path(
        "notification-settings/",
        NotificationSettingsView.as_view(),
        name="notification-settings",
    ),

    # Изменяем пароль текущего пользователя.
    path(
        "change-password/",
        ChangePasswordView.as_view(),
        name="change-password",
    ),

    # Получаем список участников конкретного Household.
    path(
        "households/<int:household_id>/members/",
        HouseholdMembersView.as_view(),
        name="household-members",
    ),

    # Изменяем роль участника Household.
    path(
        "households/<int:household_id>/members/<int:member_id>/",
        HouseholdMemberDetailView.as_view(),
        name="household-member-detail",
    ),
]


router = DefaultRouter()

# Регистрируем основные CRUD-операции для Household.
router.register(
    "households",
    HouseholdViewSet,
    basename="household",
)

# Добавляем маршруты HouseholdViewSet к уже существующим URL.
urlpatterns += router.urls