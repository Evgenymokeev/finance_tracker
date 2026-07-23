from django.db.models import Sum
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from expenses.models import Expense

from .serializers import DashboardSerializer


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
