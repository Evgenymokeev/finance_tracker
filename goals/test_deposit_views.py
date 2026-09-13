from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    FinancialGoal,
    GoalSavingTransaction,
)


class FinancialGoalDepositViewTests(APITestCase):

    def setUp(self):
        """
        Подготавливает пользователя и финансовую цель
        перед каждым тестом.

        Для каждого теста создаётся отдельная финансовая цель,
        чтобы изменения current_amount и status в одном тесте
        не влияли на другие тесты.
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

        self.client.force_authenticate(
            user=self.user
        )

    def get_deposit_url(self, goal):
        """
        Возвращает URL endpoint для пополнения
        указанной финансовой цели.
        """

        return f"/api/v1/goals/{goal.id}/deposit/"

    def test_deposit_increases_current_amount(self):
        """
        Проверяет успешное пополнение финансовой цели.

        После POST-запроса на /deposit/
        current_amount должен увеличиться
        на переданную сумму.
        """

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "5000.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("15000.00"),
        )

    def test_deposit_completes_goal_when_target_reached(self):
        """
        Проверяет автоматическое завершение финансовой цели.

        Если после пополнения current_amount достигает
        target_amount, статус цели должен измениться
        на COMPLETED.
        """

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "40000.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("50000.00"),
        )

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.COMPLETED,
        )

    def test_deposit_cannot_exceed_target_amount(self):
        """
        Проверяет, что current_amount не становится больше
        target_amount.

        Если пользователь пополняет цель на сумму,
        превышающую оставшуюся сумму до цели,
        current_amount ограничивается target_amount.
        """

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "60000.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            self.goal.target_amount,
        )

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.COMPLETED,
        )

    def test_deposit_transaction_contains_effective_amount_when_exceeding_target(self):
        """
        Проверяет сумму транзакции при пополнении,
        превышающем оставшуюся сумму до цели.

        Например:

        target_amount = 50000
        current_amount = 10000
        requested deposit = 60000

        Фактически в цель можно добавить только 40000.

        Поэтому:

        - current_amount должен стать 50000;
        - GoalSavingTransaction.amount должен быть 40000.

        История должна отражать фактически зачисленную сумму,
        а не всю сумму, переданную в запросе.
        """

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "60000.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("50000.00"),
        )

        transaction = GoalSavingTransaction.objects.get(
            goal=self.goal
        )

        self.assertEqual(
            transaction.amount,
            Decimal("40000.00"),
        )

        self.assertEqual(
            transaction.transaction_type,
            GoalSavingTransaction.TransactionType.DEPOSIT,
        )

        self.assertEqual(
            transaction.source,
            GoalSavingTransaction.Source.MANUAL,
        )

    def test_deposit_to_cancelled_goal_is_forbidden(self):
        """
        Проверяет, что отменённую финансовую цель
        нельзя пополнять.

        Endpoint должен вернуть HTTP 400,
        а current_amount не должен измениться.
        """

        self.goal.status = (
            FinancialGoal.Status.CANCELLED
        )
        self.goal.save()

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "5000.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("10000.00"),
        )

    def test_deposit_requires_positive_amount(self):
        """
        Проверяет валидацию суммы пополнения.

        Сумма должна быть больше нуля.
        Нулевое значение не должно приниматься.
        """

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "0.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("10000.00"),
        )

    def test_deposit_requires_amount(self):
        """
        Проверяет, что поле amount обязательно
        для пополнения финансовой цели.
        """

        url = self.get_deposit_url(
            self.goal
        )

        response = self.client.post(
            url,
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("10000.00"),
        )

    def test_unauthenticated_user_cannot_deposit(self):
        """
        Проверяет защиту endpoint от неавторизованных пользователей.

        Пользователь без авторизации не должен иметь возможность
        пополнять финансовую цель.
        """

        self.client.force_authenticate(
            user=None
        )

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "5000.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("10000.00"),
        )

    def test_user_cannot_deposit_to_another_users_goal(self):
        """
        Проверяет изоляцию финансовых целей между пользователями.

        Авторизованный пользователь не должен иметь возможности
        пополнять цель, принадлежащую другому пользователю.

        Ожидается HTTP 404, потому что get_queryset()
        FinancialGoalViewSet возвращает только цели
        текущего пользователя.
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

        url = self.get_deposit_url(
            another_goal
        )

        data = {
            "amount": "5000.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        another_goal.refresh_from_db()

        self.assertEqual(
            another_goal.current_amount,
            Decimal("20000.00"),
        )

    def test_deposit_creates_saving_transaction(self):
        """
        Проверяет создание записи истории после успешного
        ручного пополнения финансовой цели.

        После manual deposit должны произойти две операции:

        1. current_amount финансовой цели увеличивается;
        2. создаётся GoalSavingTransaction.

        Для manual deposit ожидаем:

        - transaction_type = deposit;
        - source = manual;
        - amount = сумма пополнения;
        - goal = текущая финансовая цель;
        - automatic_saving = None.

        Этот тест пока должен упасть, потому что мы ещё
        не добавили создание GoalSavingTransaction
        в метод deposit() представления.
        """

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "5000.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        transaction = GoalSavingTransaction.objects.get(
            goal=self.goal
        )

        self.assertEqual(
            transaction.amount,
            Decimal("5000.00"),
        )

        self.assertEqual(
            transaction.transaction_type,
            GoalSavingTransaction.TransactionType.DEPOSIT,
        )

        self.assertEqual(
            transaction.source,
            GoalSavingTransaction.Source.MANUAL,
        )

        self.assertIsNone(
            transaction.automatic_saving
        )

        self.assertEqual(
            transaction.goal,
            self.goal,
        )


    def test_cancelled_goal_does_not_create_saving_transaction(self):
        """
        Проверяет, что при попытке пополнить отменённую цель
        запись GoalSavingTransaction не создаётся.

        Отменённая цель должна отклонить операцию ещё до изменения
        current_amount и создания записи истории.
        """

        self.goal.status = (
            FinancialGoal.Status.CANCELLED
        )
        self.goal.save()

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "5000.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(
            GoalSavingTransaction.objects.filter(
                goal=self.goal
            ).exists()
        )

    def test_invalid_deposit_does_not_create_saving_transaction(self):
        """
        Проверяет, что при невалидной сумме пополнения
        запись GoalSavingTransaction не создаётся.

        В данном случае передаётся нулевая сумма.
        Serializer должен отклонить запрос,
        поэтому история операций не должна измениться.
        """

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "0.00",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(
            GoalSavingTransaction.objects.filter(
                goal=self.goal
            ).exists()
        )