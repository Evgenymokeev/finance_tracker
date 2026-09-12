from django.urls import path
from rest_framework.routers import DefaultRouter

from .automatic_saving_views import GoalAutomaticSavingView
from .views import FinancialGoalViewSet


router = DefaultRouter()

router.register(
    "",
    FinancialGoalViewSet,
    basename="financial-goal",
)

urlpatterns = [
    path(
        "<int:goal_id>/automatic-saving/",
        GoalAutomaticSavingView.as_view(),
        name="goal-automatic-saving",
    ),
] + router.urls