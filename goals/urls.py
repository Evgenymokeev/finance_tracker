from rest_framework.routers import DefaultRouter

from .views import FinancialGoalViewSet


router = DefaultRouter()

router.register(
    "",
    FinancialGoalViewSet,
    basename="financial-goal",
)

urlpatterns = router.urls