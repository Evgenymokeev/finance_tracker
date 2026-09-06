from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from .models import FinancialGoal
from .serializers import FinancialGoalSerializer


class FinancialGoalSerializerTests(TestCase):

    def setUp(self):
        # Создаём пользователя для тестов.
        # Проверяем, что FinancialGoal корректно связывается с пользователем.
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
        )

    def test_valid_financial_goal(self):
        """
        Проверяет, что корректная финансовая цель
        проходит валидацию serializer.
        """

        data = {
            "title": "Накопить на MacBook",
            "target_amount": "50000.00",
            "current_amount": "32000.00",
            "deadline": "2027-03-01",
            "description": "Накопить деньги на новый MacBook",
        }

        serializer = FinancialGoalSerializer(data=data)

        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            serializer.validated_data["target_amount"],
            Decimal("50000.00"),
        )
        self.assertEqual(
            serializer.validated_data["current_amount"],
            Decimal("32000.00"),
        )

    def test_target_amount_must_be_greater_than_zero(self):
        """
        Проверяет, что target_amount должен быть больше нуля.
        """

        data = {
            "title": "Неверная цель",
            "target_amount": "0.00",
            "current_amount": "0.00",
        }

        serializer = FinancialGoalSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("target_amount", serializer.errors)

    def test_target_amount_cannot_be_negative(self):
        """
        Проверяет, что target_amount не может быть отрицательным.
        """

        data = {
            "title": "Неверная цель",
            "target_amount": "-1000.00",
            "current_amount": "0.00",
        }

        serializer = FinancialGoalSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("target_amount", serializer.errors)

    def test_current_amount_cannot_be_negative(self):
        """
        Проверяет, что current_amount не может быть отрицательным.
        """

        data = {
            "title": "Неверная цель",
            "target_amount": "10000.00",
            "current_amount": "-500.00",
        }

        serializer = FinancialGoalSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("current_amount", serializer.errors)

    def test_current_amount_cannot_exceed_target_amount(self):
        """
        Проверяет, что current_amount не может быть
        больше target_amount.
        """

        data = {
            "title": "Неверная цель",
            "target_amount": "10000.00",
            "current_amount": "15000.00",
        }

        serializer = FinancialGoalSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("current_amount", serializer.errors)

    def test_remaining_amount(self):
        """
        Проверяет правильность расчёта оставшейся суммы.
        """

        goal = FinancialGoal.objects.create(
            user=self.user,
            title="Накопить на MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("32000.00"),
        )

        serializer = FinancialGoalSerializer(goal)

        self.assertEqual(
            serializer.data["remaining_amount"],
            Decimal("18000.00"),
        )

    def test_progress_percent(self):
        """
        Проверяет правильность расчёта прогресса цели.
        """

        goal = FinancialGoal.objects.create(
            user=self.user,
            title="Накопить на MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("32000.00"),
        )

        serializer = FinancialGoalSerializer(goal)

        self.assertEqual(
            serializer.data["progress_percent"],
            64.0,
        )

    def test_status_is_read_only(self):
        """
        Проверяет, что status нельзя изменить
        через serializer.
        """

        data = {
            "title": "Накопить на MacBook",
            "target_amount": "50000.00",
            "current_amount": "50000.00",
            "status": "completed",
        }

        serializer = FinancialGoalSerializer(data=data)

        self.assertTrue(serializer.is_valid())

        self.assertNotIn(
            "status",
            serializer.validated_data,
        )

    def test_user_is_not_available_for_input(self):
        """
        Проверяет, что user нельзя передать
        через serializer.
        """

        data = {
            "title": "Накопить на MacBook",
            "target_amount": "50000.00",
            "current_amount": "10000.00",
            "user": self.user.id,
        }

        serializer = FinancialGoalSerializer(data=data)

        self.assertTrue(serializer.is_valid())

        self.assertNotIn(
            "user",
            serializer.validated_data,
        )