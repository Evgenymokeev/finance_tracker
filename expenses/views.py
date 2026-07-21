from rest_framework import viewsets

from .models import Expense
from .serializers import ExpenseSerializer


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer

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