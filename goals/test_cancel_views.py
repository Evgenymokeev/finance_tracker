from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import FinancialGoal


class FinancialGoalCancelViewTests(APITestCase):
    """
    Тесты API для отмены финансовой цели.

    Проверяем:
    - активную цель можно отменить;
    - статус active -> cancelled;
    - completed цель нельзя отменить;
    - cancelled цель нельзя отменить повторно;
    - cancelled цель нельзя пополнить;
    - cancelled цель нельзя пополнить даже частично;
    - cancelled цель нельзя пополнить после отмены;
    - чужую цель нельзя отменить;
    - несуществующая цель возвращает 404;
    - неавторизованный пользователь получает 401.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="otherpassword123",
        )

        self.client.force_authenticate(
            user=self.user
        )

        self.goal = FinancialGoal.objects.create(
            user=self.user,
            title="Накопить на MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("30000.00"),
        )

    def get_cancel_url(self, goal):
        """
        Возвращает URL endpoint для отмены конкретной цели.
        """

        return reverse(
            "financial-goal-cancel",
            kwargs={"pk": goal.id},
        )

    def test_active_goal_can_be_cancelled(self):
        """
        Активную финансовую цель можно отменить.
        """

        url = self.get_cancel_url(self.goal)

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.CANCELLED,
        )

        self.assertEqual(
            response.data["status"],
            FinancialGoal.Status.CANCELLED,
        )

    def test_cancelled_goal_keeps_current_amount(self):
        """
        Отмена цели не должна изменять накопленную сумму.
        """

        url = self.get_cancel_url(self.goal)

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("30000.00"),
        )

        self.assertEqual(
            response.data["current_amount"],
            "30000.00",
        )

    def test_cancelled_goal_keeps_progress_and_remaining_amount(self):
        """
        Отмена цели не должна изменять progress_percent
        и remaining_amount.
        """

        url = self.get_cancel_url(self.goal)

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["progress_percent"],
            60.0,
        )

        self.assertEqual(
            response.data["remaining_amount"],
            Decimal("20000.00"),
        )

    def test_completed_goal_cannot_be_cancelled(self):
        """
        Завершённую цель нельзя отменить.
        """

        self.goal.current_amount = Decimal("50000.00")
        self.goal.status = FinancialGoal.Status.COMPLETED
        self.goal.save()

        url = self.get_cancel_url(self.goal)

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "status",
            response.data,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.COMPLETED,
        )

    def test_cancelled_goal_cannot_be_cancelled_again(self):
        """
        Уже отменённую цель нельзя отменить повторно.
        """

        self.goal.status = FinancialGoal.Status.CANCELLED
        self.goal.save()

        url = self.get_cancel_url(self.goal)

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "status",
            response.data,
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.CANCELLED,
        )

    def test_cancelled_goal_cannot_receive_deposit(self):
        """
        После отмены цели нельзя выполнить deposit.
        """

        self.goal.status = FinancialGoal.Status.CANCELLED
        self.goal.save()

        url = reverse(
            "financial-goal-deposit",
            kwargs={"pk": self.goal.id},
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
            Decimal("30000.00"),
        )

    def test_cancelled_goal_cannot_be_withdrawn(self):
        """
        После отмены цели нельзя выполнить withdraw.
        """

        self.goal.status = FinancialGoal.Status.CANCELLED
        self.goal.save()

        url = reverse(
            "financial-goal-withdraw",
            kwargs={"pk": self.goal.id},
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
            Decimal("30000.00"),
        )

    def test_cannot_cancel_other_user_goal(self):
        """
        Пользователь не может отменить чужую цель.
        """

        other_goal = FinancialGoal.objects.create(
            user=self.other_user,
            title="Чужая цель",
            target_amount=Decimal("10000.00"),
            current_amount=Decimal("5000.00"),
        )

        url = self.get_cancel_url(other_goal)

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        other_goal.refresh_from_db()

        self.assertEqual(
            other_goal.status,
            FinancialGoal.Status.ACTIVE,
        )

    def test_cancel_nonexistent_goal_returns_404(self):
        """
        Отмена несуществующей цели должна вернуть 404.
        """

        url = reverse(
            "financial-goal-cancel",
            kwargs={"pk": 999999},
        )

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unauthenticated_user_cannot_cancel_goal(self):
        """
        Неавторизованный пользователь не может отменить цель.
        """

        self.client.force_authenticate(
            user=None
        )

        url = self.get_cancel_url(self.goal)

        response = self.client.post(
            url,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )