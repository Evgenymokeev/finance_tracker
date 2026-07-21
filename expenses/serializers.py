from rest_framework import serializers
from .models import Expense


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = "__all__"

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Сумма должна быть больше нуля."
            )
        return value

    def validate_title(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                "Название должно содержать минимум 3 символа."
            )
        return value