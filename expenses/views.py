from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Expense
from .serializers import ExpenseSerializer


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
        return Expense.objects.filter(
            user=self.request.user
        ).order_by("-date")

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user
        )