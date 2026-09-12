from decimal import Decimal

from django.test import SimpleTestCase

from .serializers import (
    GoalStatisticSerializer,
    GoalsAnalyticsSerializer,
)


class GoalStatisticSerializerTest(SimpleTestCase):
    """
    Проверяет сериализацию статистики одной финансовой цели.
    """

    def test_goal_statistic_serializer(self):
        """
        Проверяет, что serializer корректно
        принимает все поля статистики цели.
        """

        data = {
            "goal": "MacBook",
            "target_amount": Decimal("50000.00"),
            "current_amount": Decimal("35000.00"),
            "spent_amount": Decimal("2500.00"),
            "remaining_amount": Decimal("15000.00"),
            "progress_percent": 70.0,
        }

        serializer = GoalStatisticSerializer(
            data=data
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertEqual(
            serializer.validated_data["goal"],
            "MacBook",
        )

        self.assertEqual(
            serializer.validated_data["target_amount"],
            Decimal("50000.00"),
        )

        self.assertEqual(
            serializer.validated_data["current_amount"],
            Decimal("35000.00"),
        )

        self.assertEqual(
            serializer.validated_data["spent_amount"],
            Decimal("2500.00"),
        )

        self.assertEqual(
            serializer.validated_data["remaining_amount"],
            Decimal("15000.00"),
        )

        self.assertEqual(
            serializer.validated_data["progress_percent"],
            70.0,
        )


class GoalsAnalyticsSerializerTest(SimpleTestCase):
    """
    Проверяет сериализацию списка статистики финансовых целей.
    """

    def test_goals_analytics_serializer(self):
        """
        Проверяет, что serializer корректно
        обрабатывает список целей.
        """

        data = {
            "goals": [
                {
                    "goal": "MacBook",
                    "target_amount": Decimal("50000.00"),
                    "current_amount": Decimal("35000.00"),
                    "spent_amount": Decimal("2500.00"),
                    "remaining_amount": Decimal("15000.00"),
                    "progress_percent": 70.0,
                },
                {
                    "goal": "Отпуск",
                    "target_amount": Decimal("30000.00"),
                    "current_amount": Decimal("10000.00"),
                    "spent_amount": Decimal("5000.00"),
                    "remaining_amount": Decimal("20000.00"),
                    "progress_percent": 33.33,
                },
            ]
        }

        serializer = GoalsAnalyticsSerializer(
            data=data
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertEqual(
            len(serializer.validated_data["goals"]),
            2,
        )