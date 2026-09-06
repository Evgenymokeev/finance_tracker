from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import FinancialGoal


class FinancialGoalDepositViewTests(APITestCase):
    """
    Тесты API для пополнения финансовой цели.

    Проверяем:
    - успешное пополнение;
    - правильное увеличение current_amount;
    - автоматическое завершение цели;
    - невозможность пополнить чужую цель;
    - невозможность пополнить несуществующую цель;
    - запрет нулевой суммы;
    - запрет отрицательной суммы;
    - запрет пополнения без авторизации.
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

    def get_deposit_url(self, goal):
        """
        Возвращает URL для пополнения указанной цели.
        """

        return reverse(
            "financial-goal-deposit",
            kwargs={"pk": goal.id},
        )

    def test_deposit_increases_current_amount(self):
        """
        Проверяет успешное пополнение цели.

        Было:
        current_amount = 30000

        Пополняем:
        5000

        Должно стать:
        current_amount = 35000
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
            Decimal("35000.00"),
        )

        self.assertEqual(
            response.data["current_amount"],
            "35000.00",
        )

    def test_deposit_updates_progress_and_remaining_amount(self):
        """
        Проверяет пересчёт прогресса и оставшейся суммы.

        После пополнения:

        target_amount  = 50000
        current_amount = 40000

        progress = 80%
        remaining = 10000
        """

        url = self.get_deposit_url(
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
            80.0,
        )

        self.assertEqual(
            response.data["remaining_amount"],
            Decimal("10000.00"),
        )

    def test_deposit_completes_goal_when_target_is_reached(self):
        """
        Проверяет автоматическое завершение цели.

        Было:

        current_amount = 30000
        target_amount  = 50000

        Пополняем на 20000.

        Ожидаем:

        current_amount = 50000
        status = completed
        progress = 100%
        remaining = 0
        """

        url = self.get_deposit_url(
            self.goal
        )

        data = {
            "amount": "20000.00",
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

        self.assertEqual(
            response.data["progress_percent"],
            100.0,
        )

        self.assertEqual(
            response.data["remaining_amount"],
            Decimal("0.00"),
        )

    def test_deposit_cannot_exceed_target_amount(self):
        """
        Проверяет, что при слишком большом пополнении
        current_amount не становится больше target_amount.

        Было:

        current_amount = 30000
        target_amount  = 50000

        Пополняем на 30000.

        Ожидаем:

        current_amount = 50000
        status = completed
        """

        url = self.get_deposit_url(
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
            Decimal("50000.00"),
        )

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.COMPLETED,
        )

    def test_cannot_deposit_to_other_user_goal(self):
        """
        Проверяет защиту чужой финансовой цели.
        """

        other_goal = FinancialGoal.objects.create(
            user=self.other_user,
            title="Чужая цель",
            target_amount=Decimal("10000.00"),
            current_amount=Decimal("2000.00"),
        )

        url = self.get_deposit_url(
            other_goal
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

        other_goal.refresh_from_db()

        self.assertEqual(
            other_goal.current_amount,
            Decimal("2000.00"),
        )

    def test_deposit_to_nonexistent_goal_returns_404(self):
        """
        Проверяет обработку несуществующей цели.
        """

        url = reverse(
            "financial-goal-deposit",
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

    def test_deposit_amount_cannot_be_zero(self):
        """
        Проверяет запрет пополнения на ноль.
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

        self.assertIn(
            "amount",
            response.data,
        )

    def test_deposit_amount_cannot_be_negative(self):
        """
        Проверяет запрет отрицательного пополнения.
        """

        url = self.get_deposit_url(
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

    def test_unauthenticated_user_cannot_deposit(self):
        """
        Проверяет, что пополнять финансовые цели
        без авторизации нельзя.
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