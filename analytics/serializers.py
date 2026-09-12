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

class GoalStatisticSerializer(serializers.Serializer):
    """
    Serializer статистики по одной финансовой цели.

    Показывает:
    - название цели;
    - целевую сумму;
    - накопленную сумму;
    - сумму расходов, связанных с целью;
    - сколько осталось накопить;
    - процент прогресса.
    """

    goal = serializers.CharField()

    target_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    current_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    spent_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    remaining_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    progress_percent = serializers.FloatField()


class GoalsAnalyticsSerializer(serializers.Serializer):
    """
    Serializer списка статистики по финансовым целям.
    """

    goals = GoalStatisticSerializer(
        many=True
    )