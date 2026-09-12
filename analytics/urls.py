from django.urls import path

from .views import (
    DashboardView,
    MonthlyAnalyticsView,
    GoalsAnalyticsView,
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
    path(
        "goals/",
        GoalsAnalyticsView.as_view(),
        name="goals-analytics",
    ),
]
