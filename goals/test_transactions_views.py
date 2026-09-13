from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    FinancialGoal,
    GoalAutomaticSaving,
    GoalSavingTransaction,
)


class GoalSavingTransactionViewTests(APITestCase):

    def setUp(self):
        """
        Подготавливает пользователя, финансовую цель
        и несколько транзакций для тестов.

        Все транзакции принадлежат одной финансовой цели
        текущего пользователя.

        Это позволяет проверить:

        - получение истории;
        - порядок транзакций;
        - отображение разных типов операций;
        - изоляцию данных между пользователями.
        """

        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
        )

        self.goal = FinancialGoal.objects.create(
            user=self.user,
            title="Накопить на MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("15000.00"),
        )

        self.client.force_authenticate(
            user=self.user
        )

    def get_transactions_url(self, goal):
        """
        Возвращает URL endpoint для получения
        истории транзакций финансовой цели.
        """

        return f"/api/v1/goals/{goal.id}/transactions/"

    def test_authenticated_user_can_get_goal_transactions(self):
        """
        Проверяет получение истории транзакций
        собственной финансовой цели.

        Endpoint должен вернуть HTTP 200
        и список транзакций.
        """

        GoalSavingTransaction.objects.create(
            goal=self.goal,
            amount=Decimal("5000.00"),
            transaction_type=(
                GoalSavingTransaction.TransactionType.DEPOSIT
            ),
            source=(
                GoalSavingTransaction.Source.MANUAL
            ),
        )

        GoalSavingTransaction.objects.create(
            goal=self.goal,
            amount=Decimal("1000.00"),
            transaction_type=(
                GoalSavingTransaction.TransactionType.WITHDRAWAL
            ),
            source=(
                GoalSavingTransaction.Source.MANUAL
            ),
        )

        url = self.get_transactions_url(
            self.goal
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            2,
        )

    def test_transactions_contain_expected_fields(self):
        """
        Проверяет структуру ответа истории транзакций.

        Каждая транзакция должна содержать поля,
        определённые GoalSavingTransactionSerializer.
        """

        transaction = GoalSavingTransaction.objects.create(
            goal=self.goal,
            amount=Decimal("5000.00"),
            transaction_type=(
                GoalSavingTransaction.TransactionType.DEPOSIT
            ),
            source=(
                GoalSavingTransaction.Source.MANUAL
            ),
        )

        url = self.get_transactions_url(
            self.goal
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        transaction_data = response.data[0]

        expected_fields = {
            "id",
            "goal",
            "amount",
            "transaction_type",
            "source",
            "automatic_saving",
            "created_at",
        }

        self.assertEqual(
            set(transaction_data.keys()),
            expected_fields,
        )

        self.assertEqual(
            transaction_data["id"],
            transaction.id,
        )

        self.assertEqual(
            transaction_data["goal"],
            self.goal.id,
        )

        self.assertEqual(
            transaction_data["amount"],
            "5000.00",
        )

        self.assertEqual(
            transaction_data["transaction_type"],
            "deposit",
        )

        self.assertEqual(
            transaction_data["source"],
            "manual",
        )

        self.assertIsNone(
            transaction_data["automatic_saving"]
        )

    def test_transactions_are_ordered_by_created_at_descending(self):
        """
        Проверяет порядок истории транзакций.

        GoalSavingTransaction.Meta содержит:

            ordering = ["-created_at"]

        Поэтому сначала должна возвращаться
        самая новая транзакция.
        """

        first_transaction = GoalSavingTransaction.objects.create(
            goal=self.goal,
            amount=Decimal("1000.00"),
            transaction_type=(
                GoalSavingTransaction.TransactionType.DEPOSIT
            ),
            source=(
                GoalSavingTransaction.Source.MANUAL
            ),
        )

        second_transaction = GoalSavingTransaction.objects.create(
            goal=self.goal,
            amount=Decimal("5000.00"),
            transaction_type=(
                GoalSavingTransaction.TransactionType.DEPOSIT
            ),
            source=(
                GoalSavingTransaction.Source.MANUAL
            ),
        )

        url = self.get_transactions_url(
            self.goal
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[0]["id"],
            second_transaction.id,
        )

        self.assertEqual(
            response.data[1]["id"],
            first_transaction.id,
        )

    def test_automatic_transaction_is_returned(self):
        """
        Проверяет, что история содержит не только
        ручные операции, но и операции Automatic Saving.

        Для автоматической транзакции:

        - source = automatic;
        - transaction_type = deposit;
        - automatic_saving содержит ID настройки
          Automatic Saving.
        """

        automatic_saving = GoalAutomaticSaving.objects.create(
            goal=self.goal,
            amount=Decimal("1000.00"),
            frequency=(
                GoalAutomaticSaving.Frequency.MONTHLY
            ),
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

        url = self.get_transactions_url(
            self.goal
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        transaction_data = response.data[0]

        self.assertEqual(
            transaction_data["id"],
            transaction.id,
        )

        self.assertEqual(
            transaction_data["source"],
            "automatic",
        )

        self.assertEqual(
            transaction_data["transaction_type"],
            "deposit",
        )

        self.assertEqual(
            transaction_data["automatic_saving"],
            automatic_saving.id,
        )

    def test_empty_transaction_history_returns_empty_list(self):
        """
        Проверяет поведение цели, у которой ещё нет
        ни одной операции.

        Endpoint должен успешно вернуть HTTP 200
        и пустой список.
        """

        url = self.get_transactions_url(
            self.goal
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data,
            [],
        )

    def test_unauthenticated_user_cannot_get_transactions(self):
        """
        Проверяет защиту истории от неавторизованных пользователей.

        Без JWT-аутентификации endpoint должен вернуть
        HTTP 401 Unauthorized.
        """

        self.client.force_authenticate(
            user=None
        )

        url = self.get_transactions_url(
            self.goal
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_user_cannot_get_another_users_transactions(self):
        """
        Проверяет изоляцию истории транзакций между пользователями.

        Даже если другая финансовая цель имеет транзакции,
        текущий пользователь не должен получить к ним доступ.

        Благодаря get_queryset() финансовых целей
        чужая цель должна возвращать HTTP 404.
        """

        another_user = User.objects.create_user(
            username="anotheruser",
            password="testpassword123",
        )

        another_goal = FinancialGoal.objects.create(
            user=another_user,
            title="Чужая цель",
            target_amount=Decimal("100000.00"),
            current_amount=Decimal("20000.00"),
        )

        GoalSavingTransaction.objects.create(
            goal=another_goal,
            amount=Decimal("5000.00"),
            transaction_type=(
                GoalSavingTransaction.TransactionType.DEPOSIT
            ),
            source=(
                GoalSavingTransaction.Source.MANUAL
            ),
        )

        url = self.get_transactions_url(
            another_goal
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_transactions_are_read_only(self):
        """
        Проверяет, что endpoint истории предназначен
        только для чтения.

        История финансовых операций не должна изменяться
        через POST, PUT, PATCH или DELETE.

        На этом этапе endpoint ещё не реализован,
        поэтому после его создания эти проверки
        должны быть обеспечены маршрутизацией
        и read-only логикой.
        """

        transaction = GoalSavingTransaction.objects.create(
            goal=self.goal,
            amount=Decimal("5000.00"),
            transaction_type=(
                GoalSavingTransaction.TransactionType.DEPOSIT
            ),
            source=(
                GoalSavingTransaction.Source.MANUAL
            ),
        )

        url = self.get_transactions_url(
            self.goal
        )

        response = self.client.post(
            url,
            {
                "amount": "999999.00",
            },
            format="json",
        )

        self.assertNotEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            GoalSavingTransaction.objects.count(),
            1,
        )

        transaction.refresh_from_db()

        self.assertEqual(
            transaction.amount,
            Decimal("5000.00"),
        )