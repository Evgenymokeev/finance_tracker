from decimal import Decimal

from rest_framework import serializers

from .models import FinancialGoal


class FinancialGoalSerializer(serializers.ModelSerializer):
    """
    Serializer для создания, просмотра и изменения финансовых целей.

    Бизнес-правила:
    - target_amount должен быть больше 0;
    - current_amount не может быть отрицательным;
    - current_amount не может превышать target_amount;
    - user нельзя передать или изменить через API;
    - status нельзя произвольно изменить через API.
    """

    remaining_amount = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()

    class Meta:
        model = FinancialGoal

        fields = [
            "id",
            "title",
            "target_amount",
            "current_amount",
            "deadline",
            "description",
            "status",
            "remaining_amount",
            "progress_percent",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "user",
            "status",
            "remaining_amount",
            "progress_percent",
            "created_at",
            "updated_at",
        ]

    def validate_target_amount(self, value):
        """
        Проверяет, что целевая сумма больше нуля.
        """

        if value <= Decimal("0"):
            raise serializers.ValidationError(
                "Target amount must be greater than zero."
            )

        return value

    def validate_current_amount(self, value):
        """
        Проверяет, что текущая сумма не отрицательная.
        """

        if value < Decimal("0"):
            raise serializers.ValidationError(
                "Current amount cannot be negative."
            )

        return value

    def validate(self, attrs):
        """
        Проверяет взаимосвязь target_amount и current_amount.

        current_amount не может быть больше target_amount.
        """

        target_amount = attrs.get(
            "target_amount",
            getattr(self.instance, "target_amount", None),
        )

        current_amount = attrs.get(
            "current_amount",
            getattr(self.instance, "current_amount", Decimal("0")),
        )

        if (
            target_amount is not None
            and current_amount is not None
            and current_amount > target_amount
        ):
            raise serializers.ValidationError(
                {
                    "current_amount": (
                        "Current amount cannot exceed target amount."
                    )
                }
            )

        return attrs

    def get_remaining_amount(self, obj):
        """
        Возвращает сумму, которая осталась до достижения цели.
        """

        remaining = obj.target_amount - obj.current_amount

        return max(remaining, Decimal("0"))

    def get_progress_percent(self, obj):
        """
        Возвращает прогресс достижения цели в процентах.
        """

        if obj.target_amount <= Decimal("0"):
            return 0

        progress = (
            obj.current_amount / obj.target_amount
        ) * Decimal("100")

        return round(float(progress), 2)