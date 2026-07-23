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

class MonthlyStatisticSerializer(serializers.Serializer):

    month = serializers.CharField()

    total = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )


class MonthlyAnalyticsSerializer(serializers.Serializer):

    monthly_expenses = MonthlyStatisticSerializer(
        many=True
    )