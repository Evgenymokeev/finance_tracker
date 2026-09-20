from django.urls import path

from .views import (
    RegisterView,
    LoginView,
    RefreshView,
    ProfileView,
    ChangePasswordView,
    UserSettingsView,
    NotificationSettingsView,
)


urlpatterns = [
    path(
        "register/",
        RegisterView.as_view(),
        name="register",
    ),

    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),

    path(
        "token/refresh/",
        RefreshView.as_view(),
        name="refresh",
    ),

    path(
        "profile/",
        ProfileView.as_view(),
        name="profile",
    ),

    path(
        "settings/",
        UserSettingsView.as_view(),
        name="user-settings",
    ),

    path(
        "notification-settings/",
        NotificationSettingsView.as_view(),
        name="notification-settings",
    ),

    path(
        "change-password/",
        ChangePasswordView.as_view(),
        name="change-password",
    ),
]