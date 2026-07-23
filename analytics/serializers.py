from rest_framework import serializers


class CategoryStatisticSerializer(serializers.Serializer):

    category = serializers.CharField()

    total = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )


class DashboardSerializer(serializers.Serializer):

    total_expenses = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    current_month_expenses = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    expenses_by_category = CategoryStatisticSerializer(
        many=True
    )