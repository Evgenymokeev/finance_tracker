from datetime import datetime

from decimal import Decimal

from django.contrib.auth.models import User

from django.test import TestCase

from goals.models import FinancialGoal

from goals.serializers import GoalAutomaticSavingSerializer


class GoalAutomaticSavingSerializerTests(TestCase):

    def setUp(self):
        """
        Создаёт пользователя и финансовую цель
        для тестов Automatic Saving.
        """

        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
        )

        self.goal = FinancialGoal.objects.create(
            user=self.user,
            title="Накопить на MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("10000.00"),
        )

        self.next_run_at = datetime(
            2026,
            9,
            20,
            9,
            0,
        )

    def test_daily_frequency_is_valid(self):
        """
        Проверяет корректную настройку daily.
        """

        data = {
            "amount": "100.00",
            "frequency": "daily",
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

    def test_weekly_frequency_is_valid(self):
        """
        Проверяет корректную настройку weekly.
        """

        data = {
            "amount": "500.00",
            "frequency": "weekly",
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

    def test_monthly_frequency_is_valid(self):
        """
        Проверяет корректную настройку monthly.
        """

        data = {
            "amount": "1000.00",
            "frequency": "monthly",
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

    def test_yearly_frequency_is_valid(self):
        """
        Проверяет корректную настройку yearly.
        """

        data = {
            "amount": "10000.00",
            "frequency": "yearly",
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

    def test_custom_frequency_is_valid(self):
        """
        Проверяет корректную настройку custom
        с interval.
        """

        data = {
            "amount": "1500.00",
            "frequency": "custom",
            "interval": 14,
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

    def test_custom_frequency_requires_interval(self):
        """
        Проверяет, что custom требует interval.
        """

        data = {
            "amount": "1500.00",
            "frequency": "custom",
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "interval",
            serializer.errors,
        )

    def test_custom_interval_must_be_greater_than_zero(self):
        """
        Проверяет, что interval для custom
        должен быть больше нуля.
        """

        data = {
            "amount": "1500.00",
            "frequency": "custom",
            "interval": 0,
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "interval",
            serializer.errors,
        )

    def test_regular_frequency_cannot_have_interval(self):
        """
        Проверяет, что interval нельзя использовать
        с daily/weekly/monthly/yearly.
        """

        data = {
            "amount": "1000.00",
            "frequency": "monthly",
            "interval": 14,
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "interval",
            serializer.errors,
        )

    def test_amount_must_be_greater_than_zero(self):
        """
        Проверяет, что amount должен быть больше нуля.
        """

        data = {
            "amount": "0.00",
            "frequency": "daily",
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "amount",
            serializer.errors,
        )

    def test_amount_cannot_be_negative(self):
        """
        Проверяет, что amount не может быть отрицательным.
        """

        data = {
            "amount": "-100.00",
            "frequency": "daily",
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "amount",
            serializer.errors,
        )

    def test_goal_is_read_only(self):
        """
        Проверяет, что goal нельзя передать через API.
        """

        data = {
            "goal": self.goal.id,
            "amount": "100.00",
            "frequency": "daily",
            "next_run_at": self.next_run_at,
        }

        serializer = GoalAutomaticSavingSerializer(
            data=data
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertNotIn(
            "goal",
            serializer.validated_data,
        )