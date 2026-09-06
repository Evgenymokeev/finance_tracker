from decimal import Decimal

from rest_framework import serializers


class GoalWithdrawSerializer(serializers.Serializer):
    """
    Serializer для снятия денег с финансовой цели.

    Бизнес-правила:
    - сумма должна быть больше нуля.
    """

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    def validate_amount(self, value):
        """
        Проверяет, что сумма снятия больше нуля.
        """

        if value <= Decimal("0"):
            raise serializers.ValidationError(
                "Withdraw amount must be greater than zero."
            )

        return value