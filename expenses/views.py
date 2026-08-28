import csv
from io import BytesIO

from django.conf import settings
from django.http import HttpResponse

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.views import APIView

from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
)

from openpyxl import Workbook

from .filters import ExpenseFilter
from .importers import ExpenseCSVImporter
from .models import Expense
from .serializers import (
    ExpenseImportSerializer,
    ExpenseSerializer,
)
from .tasks import send_expense_notification


@extend_schema(
    tags=["Expenses"]
)
class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer

    permission_classes = [
        IsAuthenticated,
    ]

    filterset_class = ExpenseFilter

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
        description="Download user expenses as a CSV file.",
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="export",
    )
    def export_csv(self, request):

        response = HttpResponse(
            content_type="text/csv"
        )

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

        expenses = self.filter_queryset(
            self.get_queryset()
        )

        for expense in expenses:
            writer.writerow([
                expense.date,
                expense.title,
                expense.category.name,
                expense.amount,
                expense.description,
            ])

        return response

    @extend_schema(
        summary="Export expenses to Excel",
        description=(
            "Download user expenses as an Excel file. "
            "All expense filters are supported."
        ),
        responses={
            200: OpenApiResponse(
                description="Excel file",
            ),
        },
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="export-excel",
    )
    def export_excel(self, request):

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Expenses"

        worksheet.append([
            "Date",
            "Title",
            "Category",
            "Amount",
            "Description",
        ])

        expenses = self.filter_queryset(
            self.get_queryset()
        )

        for expense in expenses:
            worksheet.append([
                expense.date,
                expense.title,
                expense.category.name,
                float(expense.amount),
                expense.description,
            ])

        worksheet.column_dimensions["A"].width = 15
        worksheet.column_dimensions["B"].width = 25
        worksheet.column_dimensions["C"].width = 20
        worksheet.column_dimensions["D"].width = 15
        worksheet.column_dimensions["E"].width = 40

        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        response["Content-Disposition"] = (
            'attachment; filename="expenses.xlsx"'
        )

        return response


@extend_schema(
    tags=["Expenses"],
)
class ExpenseImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary="Import expenses from CSV",
        description=(
            "Upload a CSV file with expenses. "
            "Expected columns: date, title, category, amount, description."
        ),
        request=ExpenseImportSerializer,
        responses={
            200: OpenApiResponse(
                description="Import result",
            ),
        },
    )
    def post(self, request):

        serializer = ExpenseImportSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        importer = ExpenseCSVImporter(
            user=request.user
        )

        result = importer.import_file(
            serializer.validated_data["file"]
        )

        return Response(
            result,
            status=status.HTTP_200_OK,
        )