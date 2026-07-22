from django.urls import path

from .views import (
    RegisterView,
    LoginView,
    RefreshView,
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
]