from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import FinancialGoal


class FinancialGoalWithdrawViewTests(APITestCase):
    """
    Тесты API для снятия денег с финансовой цели.

    Проверяем:
    - успешное снятие;
    - правильное уменьшение current_amount;
    - пересчёт progress_percent;
    - пересчёт remaining_amount;
    - возврат completed -> active;
    - запрет снять больше накопленной суммы;
    - защиту целей разных пользователей;
    - обработку несуществующей цели;
    - запрет нулевой суммы;
    - запрет отрицательной суммы;
    - запрет операции без авторизации.
    """

    def setUp(self):
        # Создаём двух пользователей.
        # Второй пользователь нужен для проверки
        # изоляции финансовых целей.
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="otherpassword123",
        )

        # Авторизуем основного пользователя.
        self.client.force_authenticate(
            user=self.user
        )

        # Создаём финансовую цель.
        self.goal = FinancialGoal.objects.create(
            user=self.user,
            title="Накопить на MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("30000.00"),
        )

    def get_withdraw_url(self, goal):
        """
        Возвращает URL для снятия денег
        с указанной финансовой цели.
        """

        return reverse(
            "financial-goal-withdraw",
            kwargs={"pk": goal.id},
        )

    def test_withdraw_decreases_current_amount(self):
        """
        Проверяет успешное снятие денег.

        Было:

        current_amount = 30000

        Снимаем:

        5000

        Должно стать:

        current_amount = 25000
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
            Decimal("25000.00"),
        )

        self.assertEqual(
            response.data["current_amount"],
            "25000.00",
        )

    def test_withdraw_updates_progress_and_remaining_amount(self):
        """
        Проверяет пересчёт прогресса и оставшейся суммы.

        После снятия:

        target_amount  = 50000
        current_amount = 20000

        progress = 40%
        remaining = 30000
        """

        url = self.get_withdraw_url(
            self.goal
        )

        data = {
            "amount": "10000.00",
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

        self.assertEqual(
            response.data["progress_percent"],
            40.0,
        )

        self.assertEqual(
            response.data["remaining_amount"],
            Decimal("30000.00"),
        )

    def test_withdraw_from_completed_goal_changes_status_to_active(self):
        """
        Проверяет возврат цели из completed в active.

        Было:

        target_amount  = 50000
        current_amount = 50000
        status         = completed

        Снимаем:

        10000

        Ожидаем:

        current_amount = 40000
        status         = active
        progress       = 80%
        remaining      = 10000
        """

        self.goal.current_amount = Decimal("50000.00")
        self.goal.status = FinancialGoal.Status.COMPLETED
        self.goal.save()

        url = self.get_withdraw_url(
            self.goal
        )

        data = {
            "amount": "10000.00",
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
            Decimal("40000.00"),
        )

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.ACTIVE,
        )

        self.assertEqual(
            response.data["progress_percent"],
            80.0,
        )

        self.assertEqual(
            response.data["remaining_amount"],
            Decimal("10000.00"),
        )

    def test_withdraw_entire_current_amount(self):
        """
        Проверяет снятие всей текущей суммы.

        Было:

        current_amount = 30000

        Снимаем:

        30000

        Ожидаем:

        current_amount = 0
        progress = 0%
        remaining = 50000
        """

        url = self.get_withdraw_url(
            self.goal
        )

        data = {
            "amount": "30000.00",
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
            Decimal("0.00"),
        )

        self.assertEqual(
            response.data["progress_percent"],
            0.0,
        )

        self.assertEqual(
            response.data["remaining_amount"],
            Decimal("50000.00"),
        )

    def test_withdraw_cannot_exceed_current_amount(self):
        """
        Проверяет, что нельзя снять больше,
        чем накоплено в цели.

        Было:

        current_amount = 30000

        Пытаемся снять:

        40000

        Ожидаем HTTP 400.
        """

        url = self.get_withdraw_url(
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
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "amount",
            response.data,
        )

        self.goal.refresh_from_db()

        # Проверяем, что сумма в базе
        # не изменилась после неудачной операции.
        self.assertEqual(
            self.goal.current_amount,
            Decimal("30000.00"),
        )

    def test_cannot_withdraw_from_other_user_goal(self):
        """
        Проверяет защиту чужой финансовой цели.
        """

        other_goal = FinancialGoal.objects.create(
            user=self.other_user,
            title="Чужая цель",
            target_amount=Decimal("10000.00"),
            current_amount=Decimal("5000.00"),
        )

        url = self.get_withdraw_url(
            other_goal
        )

        data = {
            "amount": "2000.00",
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

        other_goal.refresh_from_db()

        # Проверяем, что чужая цель
        # вообще не была изменена.
        self.assertEqual(
            other_goal.current_amount,
            Decimal("5000.00"),
        )

    def test_withdraw_from_nonexistent_goal_returns_404(self):
        """
        Проверяет обработку несуществующей цели.
        """

        url = reverse(
            "financial-goal-withdraw",
            kwargs={"pk": 999999},
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

    def test_withdraw_amount_cannot_be_zero(self):
        """
        Проверяет запрет снятия нулевой суммы.
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

        self.assertIn(
            "amount",
            response.data,
        )

    def test_withdraw_amount_cannot_be_negative(self):
        """
        Проверяет запрет отрицательной суммы.
        """

        url = self.get_withdraw_url(
            self.goal
        )

        data = {
            "amount": "-1000.00",
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

        self.assertIn(
            "amount",
            response.data,
        )

    def test_unauthenticated_user_cannot_withdraw(self):
        """
        Проверяет, что снимать деньги с цели
        без авторизации нельзя.
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