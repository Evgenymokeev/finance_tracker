from django.urls import path

from .views import (
    DashboardView,
    MonthlyAnalyticsView,
)


urlpatterns = [

    path(
        "dashboard/",
        DashboardView.as_view(),
        name="dashboard",
    ),


    path(
        "monthly/",
        MonthlyAnalyticsView.as_view(),
        name="monthly",
    ),

]