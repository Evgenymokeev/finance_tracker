from decimal import Decimal

from django.test import TestCase

from goals.withdraw_serializers import (
    GoalWithdrawSerializer,
)


class GoalWithdrawSerializerTests(TestCase):
    """
    Тесты serializer для снятия денег
    с финансовой цели.
    """

    def test_valid_withdraw_amount(self):
        """
        Проверяет корректную сумму снятия.
        """

        data = {
            "amount": "5000.00",
        }

        serializer = GoalWithdrawSerializer(
            data=data
        )

        self.assertTrue(
            serializer.is_valid()
        )

        self.assertEqual(
            serializer.validated_data["amount"],
            Decimal("5000.00"),
        )

    def test_withdraw_amount_cannot_be_zero(self):
        """
        Проверяет, что нельзя снять нулевую сумму.
        """

        data = {
            "amount": "0.00",
        }

        serializer = GoalWithdrawSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "amount",
            serializer.errors,
        )

    def test_withdraw_amount_cannot_be_negative(self):
        """
        Проверяет, что нельзя снять отрицательную сумму.
        """

        data = {
            "amount": "-1000.00",
        }

        serializer = GoalWithdrawSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "amount",
            serializer.errors,
        )