from rest_framework import serializers

from categories.models import Category
from goals.models import FinancialGoal

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
            "goal",
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

    def validate_goal(self, value):
        """
        Проверяет, что финансовая цель принадлежит
        текущему пользователю.

        None разрешён, потому что финансовая цель
        является необязательной для расхода.

        Поэтому возможны три варианта:

        1. Собственная цель пользователя → разрешена.
        2. Чужая цель → ошибка 400.
        3. None → разрешено, расход остаётся без цели.
        """

        # Если пользователь хочет отвязать расход от цели,
        # значение будет None.
        #
        # В этом случае проверять value.user нельзя,
        # потому что у None нет атрибута user.
        if value is None:
            return value

        user = self.context["request"].user

        # Пользователь может использовать только
        # собственные финансовые цели.
        if value.user != user:
            raise serializers.ValidationError(
            "Вы не можете использовать чужую финансовую цель."
        )

        return value


class ExpenseImportSerializer(serializers.Serializer):
    file = serializers.FileField()