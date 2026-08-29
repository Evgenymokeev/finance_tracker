from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema

from .models import Budget
from .serializers import BudgetSerializer


@extend_schema(
    tags=["Budgets"],
)
class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer

    permission_classes = [
        IsAuthenticated,
    ]

    filter_backends = [
        DjangoFilterBackend,
        OrderingFilter,
    ]

    filterset_fields = [
        "category",
        "month",
    ]

    ordering_fields = [
        "amount",
        "month",
        "created_at",
        "updated_at",
    ]

    ordering = [
        "-month",
        "category__name",
    ]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Budget.objects.none()

        return (
            Budget.objects
            .filter(user=self.request.user)
            .select_related("category")
        )

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
        )
