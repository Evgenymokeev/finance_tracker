from decimal import Decimal

from django.test import TestCase

from .deposit_serializers import GoalDepositSerializer


class GoalDepositSerializerTests(TestCase):
    """
    Тесты serializer для пополнения финансовой цели.

    Проверяем:
    - корректную сумму;
    - запрет нулевой суммы;
    - запрет отрицательной суммы.
    """

    def test_valid_deposit_amount(self):
        """
        Проверяет, что положительная сумма
        проходит валидацию.
        """

        data = {
            "amount": "5000.00",
        }

        serializer = GoalDepositSerializer(
            data=data
        )

        self.assertTrue(
            serializer.is_valid()
        )

        self.assertEqual(
            serializer.validated_data["amount"],
            Decimal("5000.00"),
        )

    def test_deposit_amount_cannot_be_zero(self):
        """
        Проверяет запрет пополнения на ноль.
        """

        data = {
            "amount": "0.00",
        }

        serializer = GoalDepositSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "amount",
            serializer.errors,
        )

    def test_deposit_amount_cannot_be_negative(self):
        """
        Проверяет запрет отрицательной суммы.
        """

        data = {
            "amount": "-1000.00",
        }

        serializer = GoalDepositSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "amount",
            serializer.errors,
        )