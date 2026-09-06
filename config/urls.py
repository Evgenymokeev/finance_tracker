from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)


urlpatterns = [

    path(
        "admin/",
        admin.site.urls,
    ),


    # Goals должен находиться ВЫШЕ общего маршрута Expenses.
    #
    # Expenses использует общий prefix "api/v1/".
    # Поэтому Django иначе может попытаться обработать
    # /api/v1/goals/ через expenses.urls.
    path(
        "api/v1/goals/",
        include("goals.urls"),
    ),


    path(
        "api/v1/",
        include("expenses.urls"),
    ),


    path(
        "api/v1/categories/",
        include("categories.urls"),
    ),


    path(
        "api/v1/auth/",
        include("users.urls"),
    ),


    path(
        "api/v1/analytics/",
        include("analytics.urls"),
    ),


    path(
        "api/v1/budgets/",
        include("budgets.urls"),
    ),


    path(
        "api/v1/notifications/",
        include("notifications.urls"),
    ),


    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="schema",
    ),


    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema"
        ),
        name="swagger-ui",
    ),

]