from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from goals.models import (
    FinancialGoal,
    GoalSavingTransaction,
)
from goals.serializers import GoalSavingTransactionSerializer


class GoalSavingTransactionSerializerTests(TestCase):

    def setUp(self):
        """
        Создаёт пользователя, финансовую цель
        и транзакцию для тестов serializer.
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

        self.transaction = GoalSavingTransaction.objects.create(
            goal=self.goal,
            amount=Decimal("500.00"),
            transaction_type=(
                GoalSavingTransaction.TransactionType.DEPOSIT
            ),
            source=(
                GoalSavingTransaction.Source.MANUAL
            ),
        )

    def test_valid_transaction_is_serialized(self):
        """
        Проверяет, что существующая транзакция
        корректно сериализуется.
        """

        serializer = GoalSavingTransactionSerializer(
            self.transaction
        )

        self.assertEqual(
            serializer.data["id"],
            self.transaction.id,
        )

        self.assertEqual(
            serializer.data["goal"],
            self.goal.id,
        )

        self.assertEqual(
            serializer.data["amount"],
            "500.00",
        )

        self.assertEqual(
            serializer.data["transaction_type"],
            "deposit",
        )

        self.assertEqual(
            serializer.data["source"],
            "manual",
        )

        self.assertIsNone(
            serializer.data["automatic_saving"]
        )

        self.assertIsNotNone(
            serializer.data["created_at"]
        )

    def test_all_transaction_fields_are_read_only(self):
        """
        Проверяет, что все поля GoalSavingTransaction
        доступны только для чтения.

        Клиент не должен иметь возможность изменять
        историю финансовых операций через serializer.
        """

        serializer = GoalSavingTransactionSerializer(
            self.transaction
        )

        read_only_fields = [
            "id",
            "goal",
            "amount",
            "transaction_type",
            "source",
            "automatic_saving",
            "created_at",
        ]

        for field_name in read_only_fields:
            self.assertTrue(
                serializer.fields[field_name].read_only,
                f"{field_name} должен быть read-only.",
            )

    def test_transaction_fields_are_not_available_for_input(self):
        """
        Проверяет, что значения полей транзакции,
        переданные клиентом, не попадают
        в validated_data.

        Это защищает историю от ручной подделки
        через serializer.
        """

        data = {
            "goal": self.goal.id,
            "amount": "999999.00",
            "transaction_type": "withdrawal",
            "source": "automatic",
            "automatic_saving": 999,
        }

        serializer = GoalSavingTransactionSerializer(
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

        self.assertNotIn(
            "amount",
            serializer.validated_data,
        )

        self.assertNotIn(
            "transaction_type",
            serializer.validated_data,
        )

        self.assertNotIn(
            "source",
            serializer.validated_data,
        )

        self.assertNotIn(
            "automatic_saving",
            serializer.validated_data,
        )

        self.assertNotIn(
            "created_at",
            serializer.validated_data,
        )

    def test_automatic_transaction_is_serialized(self):
        """
        Проверяет, что автоматическая транзакция
        корректно отображается в serializer.

        В отличие от manual-транзакции,
        automatic_saving должен содержать
        идентификатор настройки Automatic Saving.
        """

        from goals.models import GoalAutomaticSaving

        automatic_saving = GoalAutomaticSaving.objects.create(
            goal=self.goal,
            amount=Decimal("1000.00"),
            frequency=GoalAutomaticSaving.Frequency.MONTHLY,
            next_run_at=timezone.now(),
        )

        transaction = GoalSavingTransaction.objects.create(
            goal=self.goal,
            automatic_saving=automatic_saving,
            amount=Decimal("1000.00"),
            transaction_type=(
                GoalSavingTransaction.TransactionType.DEPOSIT
            ),
            source=(
                GoalSavingTransaction.Source.AUTOMATIC
            ),
        )

        serializer = GoalSavingTransactionSerializer(
            transaction
        )

        self.assertEqual(
            serializer.data["source"],
            "automatic",
        )

        self.assertEqual(
            serializer.data["transaction_type"],
            "deposit",
        )

        self.assertEqual(
            serializer.data["automatic_saving"],
            automatic_saving.id,
        )