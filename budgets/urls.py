from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BudgetViewSet


router = DefaultRouter()

router.register(
    "",
    BudgetViewSet,
    basename="budget",
)


urlpatterns = [
    path(
        "",
        include(router.urls),
    ),
]