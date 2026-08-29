from rest_framework import serializers

from .models import Budget


class BudgetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )

    class Meta:
        model = Budget
        fields = [
            "id",
            "category",
            "category_name",
            "amount",
            "month",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "category_name",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Budget amount must be greater than zero."
            )

        return value

    def validate_category(self, value):
        request = self.context.get("request")

        if request and request.user.is_authenticated:
            if value.user != request.user:
                raise serializers.ValidationError(
                    "You cannot use another user's category."
                )

        return value

    def validate_month(self, value):
        if value.day != 1:
            raise serializers.ValidationError(
                "Month must be the first day of the month."
            )

        return value

    def validate(self, attrs):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return attrs

        category = attrs.get("category")
        month = attrs.get("month")

        if category is None or month is None:
            return attrs

        queryset = Budget.objects.filter(
            user=request.user,
            category=category,
            month=month,
        )

        # При обновлении разрешаем сохранить текущий бюджет.
        if self.instance is not None:
            queryset = queryset.exclude(
                pk=self.instance.pk,
            )

        if queryset.exists():
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "A budget for this category and month already exists."
                    ]
                }
            )

        return attrs