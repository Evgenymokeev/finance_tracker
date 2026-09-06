from decimal import Decimal

from rest_framework import serializers


class GoalDepositSerializer(serializers.Serializer):
    """
    Serializer для операции пополнения финансовой цели.

    Проверяет:
    - amount должен быть указан;
    - amount должен быть больше нуля.
    """

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    def validate_amount(self, value):
        """
        Проверяет, что сумма пополнения положительная.
        """

        if value <= Decimal("0"):
            raise serializers.ValidationError(
                "Deposit amount must be greater than zero."
            )

        return value