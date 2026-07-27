from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from .tasks import send_expense_notification
from .models import Expense
from .serializers import ExpenseSerializer
from django.conf import settings


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

        return Expense.objects.filter(
            user=self.request.user
        ).order_by("-date")


    def perform_create(self, serializer):
        expense = serializer.save(user=self.request.user)

        if not settings.TESTING:
            send_expense_notification.delay(expense.id)