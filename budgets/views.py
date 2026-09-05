from decimal import Decimal

from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from expenses.models import Expense

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

    @extend_schema(
        responses={200: dict},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="progress",
    )
    def progress(self, request, pk=None):
        budget = self.get_object()

        start_date = budget.month

        if budget.month.month == 12:
            next_month = budget.month.replace(
                year=budget.month.year + 1,
                month=1,
                day=1,
            )
        else:
            next_month = budget.month.replace(
                month=budget.month.month + 1,
                day=1,
            )

        spent_amount = (
            Expense.objects
            .filter(
                user=request.user,
                category=budget.category,
                date__gte=start_date,
                date__lt=next_month,
            )
            .aggregate(
                total=Sum("amount"),
            )
            ["total"]
            or Decimal("0.00")
        )

        remaining_amount = budget.amount - spent_amount

        percentage = (
            (spent_amount / budget.amount) * Decimal("100")
            if budget.amount > 0
            else Decimal("0.00")
        )

        return Response(
            {
                "budget_id": budget.id,
                "category": budget.category.name,
                "month": budget.month,
                "budget_amount": f"{budget.amount:.2f}",
                "spent_amount": f"{spent_amount:.2f}",
                "remaining_amount": f"{remaining_amount:.2f}",
                "percentage_used": float(percentage),
                "is_exceeded": spent_amount > budget.amount,
            },
            status=status.HTTP_200_OK,
        )
