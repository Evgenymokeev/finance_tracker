from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from categories.models import Category
from expenses.models import Expense


class ExpenseAPITest(APITestCase):

    def setUp(self):
        # Первый пользователь
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Еда"
        )

        self.client.force_authenticate(user=self.user)

    def test_create_expense(self):
        data = {
            "title": "Кофе",
            "amount": "80.00",
            "category": self.category.id,
            "date": "2026-07-23",
            "description": "Latte"
        }

        response = self.client.post(
            "/api/v1/expenses/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertEqual(
            Expense.objects.count(),
            1
        )

        expense = Expense.objects.first()

        self.assertEqual(
            expense.user,
            self.user
        )

    def test_unauthorized_user_cannot_create_expense(self):
        self.client.force_authenticate(user=None)

        data = {
            "title": "Coffee",
            "amount": "120.00",
            "category": self.category.id,
            "date": "2026-07-24",
            "description": "Latte"
        }

        response = self.client.post(
            "/api/v1/expenses/",
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_user_sees_only_own_expenses(self):
        second_user = User.objects.create_user(
            username="seconduser",
            password="testpass123"
        )

        second_category = Category.objects.create(
            user=second_user,
            name="Транспорт"
        )

        Expense.objects.create(
            user=self.user,
            title="Кофе",
            amount="80.00",
            category=self.category,
            date="2026-07-23"
        )

        Expense.objects.create(
            user=second_user,
            title="Автобус",
            amount="40.00",
            category=second_category,
            date="2026-07-23"
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/expenses/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            len(response.data["results"]),
            1
        )

        self.assertEqual(
            response.data["results"][0]["title"],
            "Кофе"
        )

    def test_cannot_create_expense_with_foreign_category(self):
        second_user = User.objects.create_user(
            username="seconduser",
            password="testpass123"
        )

        foreign_category = Category.objects.create(
            user=second_user,
            name="Чужая категория"
        )

        data = {
            "title": "Кофе",
            "amount": "80.00",
            "category": foreign_category.id,
            "date": "2026-07-23",
            "description": "Latte"
        }

        response = self.client.post(
            "/api/v1/expenses/",
            data
        )
    
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            Expense.objects.count(),
            0
        )

    def test_export_expenses_to_csv(self):
        Expense.objects.create(
            user=self.user,
            title="Кофе",
            amount="80.00",
            category=self.category,
            date="2026-07-23",
            description="Latte"
        )

        response = self.client.get(
            "/api/v1/expenses/export/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response["Content-Type"],
            "text/csv"
        )

        self.assertIn(
            "attachment",
            response["Content-Disposition"]
        )

        content = response.content.decode("utf-8")

        self.assertIn(
            "Date,Title,Category,Amount,Description",
            content
        )

        self.assertIn(
            "Кофе",
            content
        )

        self.assertIn(
            "Еда",
            content
        )
# Create your tests here.
