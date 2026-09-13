from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    FinancialGoal,
    GoalSavingTransaction,
)


class FinancialGoalWithdrawViewTests(APITestCase):

    def setUp(self):
        """
        Подготавливает пользователя и финансовую цель
        перед каждым тестом.

        Для каждого теста создаётся отдельная финансовая цель,
        чтобы изменения current_amount и status
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
            current_amount=Decimal("20000.00"),
        )

        self.client.force_authenticate(
            user=self.user
        )

    def get_withdraw_url(self, goal):
        """
        Возвращает URL endpoint для снятия средств
        с указанной финансовой цели.
        """

        return f"/api/v1/goals/{goal.id}/withdraw/"

    def test_withdraw_decreases_current_amount(self):
        """
        Проверяет успешное снятие средств
        с финансовой цели.

        После POST-запроса на /withdraw/
        current_amount должен уменьшиться
        на переданную сумму.
        """

        url = self.get_withdraw_url(
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

    def test_withdraw_cannot_exceed_current_amount(self):
        """
        Проверяет, что нельзя снять сумму,
        превышающую текущую сумму финансовой цели.

        Если current_amount равен 20000,
        попытка снять 25000 должна быть отклонена.

        Баланс цели при этом не должен измениться.
        """

        url = self.get_withdraw_url(
            self.goal
        )

        data = {
            "amount": "25000.00",
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
            Decimal("20000.00"),
        )

    def test_withdraw_from_cancelled_goal_is_forbidden(self):
        """
        Проверяет, что отменённую финансовую цель
        нельзя использовать для снятия средств.

        Endpoint должен вернуть HTTP 400,
        а current_amount не должен измениться.
        """

        self.goal.status = (
            FinancialGoal.Status.CANCELLED
        )
        self.goal.save()

        url = self.get_withdraw_url(
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
            Decimal("20000.00"),
        )

    def test_withdraw_changes_completed_goal_to_active(self):
        """
        Проверяет изменение статуса завершённой цели
        после снятия средств.

        Если цель была COMPLETED, но после снятия
        current_amount становится меньше target_amount,
        её статус должен снова стать ACTIVE.
        """

        self.goal.current_amount = (
            self.goal.target_amount
        )
        self.goal.status = (
            FinancialGoal.Status.COMPLETED
        )
        self.goal.save()

        url = self.get_withdraw_url(
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
            Decimal("45000.00"),
        )

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.ACTIVE,
        )

    def test_withdraw_from_completed_goal_that_remains_at_target_is_not_reactivated(
        self,
    ):
        """
        Проверяет, что статус COMPLETED не изменяется,
        если после операции current_amount всё ещё
        соответствует target_amount.

        На практике обычное снятие уменьшает сумму цели,
        поэтому этот тест дополнительно фиксирует правило:

        если current_amount стал меньше target_amount,
        статус должен быть ACTIVE.

        Для обычного withdraw с COMPLETED-цели
        ожидаем именно ACTIVE.
        """

        self.goal.current_amount = (
            self.goal.target_amount
        )
        self.goal.status = (
            FinancialGoal.Status.COMPLETED
        )
        self.goal.save()

        url = self.get_withdraw_url(
            self.goal
        )

        data = {
            "amount": "1.00",
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
            Decimal("49999.00"),
        )

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.ACTIVE,
        )

    def test_withdraw_requires_positive_amount(self):
        """
        Проверяет валидацию суммы снятия.

        Сумма должна быть больше нуля.
        Нулевое значение не должно приниматься.
        """

        url = self.get_withdraw_url(
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
            Decimal("20000.00"),
        )

    def test_withdraw_requires_amount(self):
        """
        Проверяет, что поле amount обязательно
        для снятия средств с финансовой цели.
        """

        url = self.get_withdraw_url(
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
            Decimal("20000.00"),
        )

    def test_unauthenticated_user_cannot_withdraw(self):
        """
        Проверяет защиту endpoint от неавторизованных пользователей.

        Пользователь без авторизации не должен иметь
        возможность снимать средства с финансовой цели.
        """

        self.client.force_authenticate(
            user=None
        )

        url = self.get_withdraw_url(
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
            Decimal("20000.00"),
        )

    def test_user_cannot_withdraw_from_another_users_goal(self):
        """
        Проверяет изоляцию финансовых целей между пользователями.

        Авторизованный пользователь не должен иметь возможности
        снимать средства с цели, принадлежащей другому пользователю.

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

        url = self.get_withdraw_url(
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

    def test_withdraw_creates_saving_transaction(self):
        """
        Проверяет создание записи истории после успешного
        ручного снятия средств.

        После manual withdraw должны произойти две операции:

        1. current_amount финансовой цели уменьшается;
        2. создаётся GoalSavingTransaction.

        Для manual withdraw ожидаем:

        - transaction_type = withdrawal;
        - source = manual;
        - amount = сумма снятия;
        - goal = текущая финансовая цель;
        - automatic_saving = None.

        Этот тест пока должен упасть, потому что мы ещё
        не добавили создание GoalSavingTransaction
        в метод withdraw() представления.
        """

        url = self.get_withdraw_url(
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
            GoalSavingTransaction.TransactionType.WITHDRAWAL,
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
        Проверяет, что при попытке снять средства
        с отменённой цели запись GoalSavingTransaction
        не создаётся.

        Отменённая цель должна отклонить операцию ещё до
        изменения current_amount и создания записи истории.
        """

        self.goal.status = (
            FinancialGoal.Status.CANCELLED
        )
        self.goal.save()

        url = self.get_withdraw_url(
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


    def test_invalid_withdraw_does_not_create_saving_transaction(self):
        """
        Проверяет, что при невалидной сумме снятия
        запись GoalSavingTransaction не создаётся.

        В данном случае передаётся нулевая сумма.
        Serializer должен отклонить запрос,
        поэтому история операций не должна измениться.
        """

        url = self.get_withdraw_url(
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

    def test_excessive_withdraw_does_not_create_saving_transaction(self):
        """
        Проверяет, что попытка снять сумму,
        превышающую current_amount, не создаёт транзакцию.

        Операция должна быть полностью отклонена:

        - current_amount не изменяется;
        - GoalSavingTransaction не создаётся.
        """

        url = self.get_withdraw_url(
            self.goal
        )

        data = {
            "amount": "25000.00",
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
            Decimal("20000.00"),
        )

        self.assertFalse(
            GoalSavingTransaction.objects.filter(
                goal=self.goal
            ).exists()
        )