from django.db.models import Sum
from django.utils import timezone
from django.db.models.functions import TruncMonth

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from decimal import Decimal
from drf_spectacular.utils import extend_schema

from expenses.models import Expense
from goals.models import FinancialGoal

from .serializers import (
    DashboardSerializer,
    MonthlyAnalyticsSerializer,
    GoalsAnalyticsSerializer,
)


@extend_schema(
    tags=["Analytics"],
    responses=DashboardSerializer,
)
class DashboardView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        user = request.user

        total_expenses = Expense.objects.filter(
            user=user
        ).aggregate(
            total=Sum("amount")
        )["total"] or 0


        now = timezone.now()

        current_month_expenses = Expense.objects.filter(
            user=user,
            date__year=now.year,
            date__month=now.month,
        ).aggregate(
            total=Sum("amount")
        )["total"] or 0


        expenses_by_category = Expense.objects.filter(
            user=user
        ).values(
            "category__name"
        ).annotate(
            total=Sum("amount")
        ).order_by(
            "-total"
        )


        data = {
            "total_expenses": total_expenses,

            "current_month_expenses": current_month_expenses,

            "expenses_by_category": [
                {
                    "category": item["category__name"],
                    "total": item["total"],
                }
                for item in expenses_by_category
            ],
        }


        serializer = DashboardSerializer(
            data=data
        )

        serializer.is_valid(
            raise_exception=True
        )

        return Response(
            serializer.data
        )

# Create your views here.
@extend_schema(
    tags=["Analytics"],
    responses=MonthlyAnalyticsSerializer,
)
class MonthlyAnalyticsView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]


    def get(self, request):

        user = request.user


        monthly_expenses = Expense.objects.filter(
            user=user
        ).annotate(
            month=TruncMonth("date")
        ).values(
            "month"
        ).annotate(
            total=Sum("amount")
        ).order_by(
            "month"
        )


        data = {
            "monthly_expenses": [
                {
                    "month": item["month"].strftime("%Y-%m"),
                    "total": item["total"],
                }
                for item in monthly_expenses
            ]
        }


        serializer = MonthlyAnalyticsSerializer(
            data=data
        )

        serializer.is_valid(
            raise_exception=True
        )


        return Response(
            serializer.data
        )

@extend_schema(
    tags=["Analytics"],
    responses=GoalsAnalyticsSerializer,
)
class GoalsAnalyticsView(APIView):
    """
    Возвращает аналитику по финансовым целям
    текущего пользователя.

    Для каждой цели показывает:

    - target_amount — целевая сумма;
    - current_amount — уже накопленная сумма;
    - spent_amount — сумма расходов, связанных с целью;
    - remaining_amount — сколько осталось накопить;
    - progress_percent — процент выполнения цели.

    Важно:

    spent_amount НЕ изменяет current_amount.

    Expense, связанный с целью, означает только то,
    что данный расход относится к этой цели.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        goals = (
            FinancialGoal.objects
            .filter(
                user=request.user
            )
            .annotate(
                spent_amount=Sum(
                    "expenses__amount"
                )
            )
        )

        data = {
            "goals": [],
        }

        for goal in goals:

            spent_amount = (
                goal.spent_amount
                or Decimal("0.00")
            )

            remaining_amount = max(
                goal.target_amount
                - goal.current_amount,
                Decimal("0.00"),
            )

            if goal.target_amount > Decimal("0"):

                progress_percent = (
                    goal.current_amount
                    / goal.target_amount
                ) * Decimal("100")

                progress_percent = (
                    progress_percent.quantize(
                        Decimal("0.01")
                    )
                )

            else:
                progress_percent = Decimal("0.00")

            data["goals"].append(
                {
                    "goal": goal.title,
                    "target_amount": goal.target_amount,
                    "current_amount": goal.current_amount,
                    "spent_amount": spent_amount,
                    "remaining_amount": remaining_amount,
                    "progress_percent": progress_percent,
                }
            )

        serializer = GoalsAnalyticsSerializer(
            data=data
        )

        serializer.is_valid(
            raise_exception=True
        )

        return Response(
            serializer.data
        )
