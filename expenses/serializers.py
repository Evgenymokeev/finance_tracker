from rest_framework import serializers

from categories.models import Category
from .models import Expense


class ExpenseSerializer(serializers.ModelSerializer):

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )


    class Meta:
        model = Expense

        fields = [
            "id",
            "title",
            "amount",
            "category",
            "category_name",
            "date",
            "description",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "category_name",
        ]


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


    def validate_category(self, value):

        user = self.context["request"].user

        if value.user != user:
            raise serializers.ValidationError(
                "Вы не можете использовать чужую категорию."
            )

        return value