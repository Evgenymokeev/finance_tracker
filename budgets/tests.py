from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.test import APITestCase

from categories.models import Category

from .models import Budget


class BudgetAPITest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Еда",
        )

        self.client.force_authenticate(
            user=self.user,
        )

    def test_create_budget(self):
        data = {
            "category": self.category.id,
            "amount": "10000.00",
            "month": "2026-08-01",
        }

        response = self.client.post(
            "/api/v1/budgets/",
            data,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            Budget.objects.count(),
            1,
        )

        budget = Budget.objects.first()

        self.assertEqual(
            budget.user,
            self.user,
        )

        self.assertEqual(
            budget.category,
            self.category,
        )

        self.assertEqual(
            str(budget.amount),
            "10000.00",
        )

    def test_user_sees_only_own_budgets(self):
        second_user = User.objects.create_user(
            username="seconduser",
            password="testpass123",
        )

        second_category = Category.objects.create(
            user=second_user,
            name="Транспорт",
        )

        Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Budget.objects.create(
            user=second_user,
            category=second_category,
            amount="5000.00",
            month="2026-08-01",
        )

        response = self.client.get(
            "/api/v1/budgets/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["category_name"],
            "Еда",
        )

    def test_cannot_create_budget_with_foreign_category(self):
        second_user = User.objects.create_user(
            username="seconduser",
            password="testpass123",
        )

        foreign_category = Category.objects.create(
            user=second_user,
            name="Чужая категория",
        )

        data = {
            "category": foreign_category.id,
            "amount": "10000.00",
            "month": "2026-08-01",
        }

        response = self.client.post(
            "/api/v1/budgets/",
            data,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Budget.objects.count(),
            0,
        )

    def test_cannot_create_budget_with_zero_amount(self):
        data = {
            "category": self.category.id,
            "amount": "0.00",
            "month": "2026-08-01",
        }

        response = self.client.post(
            "/api/v1/budgets/",
            data,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Budget.objects.count(),
            0,
        )

    def test_cannot_create_budget_with_negative_amount(self):
        data = {
            "category": self.category.id,
            "amount": "-100.00",
            "month": "2026-08-01",
        }

        response = self.client.post(
            "/api/v1/budgets/",
            data,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Budget.objects.count(),
            0,
        )

    def test_cannot_create_budget_with_invalid_month(self):
        data = {
            "category": self.category.id,
            "amount": "10000.00",
            "month": "2026-08-15",
        }

        response = self.client.post(
            "/api/v1/budgets/",
            data,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Budget.objects.count(),
            0,
        )

    def test_cannot_create_duplicate_budget_for_same_category_and_month(
        self,
    ):
        Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        data = {
            "category": self.category.id,
            "amount": "15000.00",
            "month": "2026-08-01",
        }

        response = self.client.post(
            "/api/v1/budgets/",
            data,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Budget.objects.count(),
            1,
        )

    def test_update_budget(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        data = {
            "category": self.category.id,
            "amount": "15000.00",
            "month": "2026-08-01",
        }

        response = self.client.put(
            f"/api/v1/budgets/{budget.id}/",
            data,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        budget.refresh_from_db()

        self.assertEqual(
            str(budget.amount),
            "15000.00",
        )

    def test_delete_budget(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        response = self.client.delete(
            f"/api/v1/budgets/{budget.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertEqual(
            Budget.objects.count(),
            0,
        )

    def test_unauthorized_user_cannot_create_budget(self):
        self.client.force_authenticate(
            user=None,
        )

        data = {
            "category": self.category.id,
            "amount": "10000.00",
            "month": "2026-08-01",
        }

        response = self.client.post(
            "/api/v1/budgets/",
            data,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            Budget.objects.count(),
            0,
        )

    def test_unauthorized_user_cannot_list_budgets(self):
        self.client.force_authenticate(
            user=None,
        )

        response = self.client.get(
            "/api/v1/budgets/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_user_cannot_access_another_users_budget(self):
        second_user = User.objects.create_user(
            username="seconduser",
            password="testpass123",
        )

        second_category = Category.objects.create(
            user=second_user,
            name="Транспорт",
        )

        budget = Budget.objects.create(
            user=second_user,
            category=second_category,
            amount="5000.00",
            month="2026-08-01",
        )

        response = self.client.get(
            f"/api/v1/budgets/{budget.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_filter_budgets_by_category(self):
        second_category = Category.objects.create(
            user=self.user,
            name="Транспорт",
        )

        Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Budget.objects.create(
            user=self.user,
            category=second_category,
            amount="5000.00",
            month="2026-08-01",
        )

        response = self.client.get(
            "/api/v1/budgets/",
            {
                "category": self.category.id,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["category_name"],
            "Еда",
        )

    def test_filter_budgets_by_month(self):
        Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="12000.00",
            month="2026-09-01",
        )

        response = self.client.get(
            "/api/v1/budgets/",
            {
                "month": "2026-08-01",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

        self.assertEqual(
            response.data["results"][0]["month"],
            "2026-08-01",
        )
