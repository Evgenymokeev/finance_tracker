import django_filters

from .models import Expense


class ExpenseFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(
        field_name="date",
        lookup_expr="gte",
    )

    date_to = django_filters.DateFilter(
        field_name="date",
        lookup_expr="lte",
    )

    amount_from = django_filters.NumberFilter(
        field_name="amount",
        lookup_expr="gte",
    )

    amount_to = django_filters.NumberFilter(
        field_name="amount",
        lookup_expr="lte",
    )

    goal = django_filters.NumberFilter(
        field_name="goal",
    )

    class Meta:
        model = Expense
        fields = [
            "category",
            "goal",
            "date",
            "date_from",
            "date_to",
            "amount_from",
            "amount_to",
        ]