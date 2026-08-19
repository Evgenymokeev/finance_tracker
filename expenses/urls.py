from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ExpenseImportView, ExpenseViewSet


router = DefaultRouter()

router.register(
    "expenses",
    ExpenseViewSet,
    basename="expenses",
)

urlpatterns = [
    path(
        "expenses/import/",
        ExpenseImportView.as_view(),
        name="expense-import",
    ),
]

urlpatterns += router.urls