from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from .models import FinancialGoal


class FinancialGoalModelTests(TestCase):

    def setUp(self):
        # Создаём пользователя для тестов.
        # Проверяем, что FinancialGoal корректно связывается с пользователем.
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
        )

    def test_create_financial_goal(self):
        """
        Проверяет создание финансовой цели
        со всеми основными полями.
        """

        goal = FinancialGoal.objects.create(
            user=self.user,
            title="Накопить на MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("32000.00"),
            deadline=date(2027, 3, 1),
            description="Накопить деньги на новый MacBook",
        )

        self.assertEqual(goal.title, "Накопить на MacBook")
        self.assertEqual(goal.target_amount, Decimal("50000.00"))
        self.assertEqual(goal.current_amount, Decimal("32000.00"))
        self.assertEqual(goal.deadline, date(2027, 3, 1))
        self.assertEqual(goal.status, FinancialGoal.Status.ACTIVE)
        self.assertEqual(goal.user, self.user)

    def test_default_values(self):
        """
        Проверяет значения полей по умолчанию:

        - current_amount = 0
        - description = ""
        - status = active
        """

        goal = FinancialGoal.objects.create(
            user=self.user,
            title="Emergency Fund",
            target_amount=Decimal("10000.00"),
        )

        self.assertEqual(goal.current_amount, Decimal("0"))
        self.assertEqual(goal.description, "")
        self.assertEqual(goal.status, FinancialGoal.Status.ACTIVE)

    def test_string_representation(self):
        """
        Проверяет строковое представление FinancialGoal.

        str(goal) должен возвращать название финансовой цели.
        """

        goal = FinancialGoal.objects.create(
            user=self.user,
            title="Накопить на отпуск",
            target_amount=Decimal("30000.00"),
        )

        self.assertEqual(str(goal), "Накопить на отпуск")
