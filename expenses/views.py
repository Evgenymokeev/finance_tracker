import csv

from django.conf import settings
from django.http import HttpResponse

from drf_spectacular.utils import extend_schema

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from .models import Expense
from .serializers import ExpenseSerializer
from .tasks import send_expense_notification


@extend_schema(
    tags=["Expenses"]
)
class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer

    permission_classes = [
        IsAuthenticated,
    ]

    filterset_fields = [
        "category",
        "date",
    ]

    search_fields = [
        "title",
        "description",
    ]

    ordering_fields = [
        "amount",
        "date",
        "created_at",
    ]

    def get_queryset(self):

        if getattr(self, "swagger_fake_view", False):
            return Expense.objects.none()

        return (
            Expense.objects.filter(
                user=self.request.user
            )
            .select_related("category")
            .order_by("-date")
        )

    def perform_create(self, serializer):
        expense = serializer.save(user=self.request.user)

        if not settings.TESTING:
            send_expense_notification.delay(expense.id)

    @extend_schema(
        summary="Export expenses to CSV",
        description="Download all user expenses as a CSV file.",
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export_csv(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="expenses.csv"'
        )

        writer = csv.writer(response)

        writer.writerow([
            "Date",
            "Title",
            "Category",
            "Amount",
            "Description",
        ])

        expenses = self.get_queryset()

        for expense in expenses:
            writer.writerow([
                expense.date,
                expense.title,
                expense.category.name,
                expense.amount,
                expense.description,
            ])

        return response