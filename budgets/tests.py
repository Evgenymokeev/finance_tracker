from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.test import APITestCase

from categories.models import Category
from expenses.models import Expense
from notifications.models import Notification
from .models import Budget
from .tasks import check_budget_exceeded


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

    def test_budget_progress(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="15000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Кофе",
            amount="500.00",
            category=self.category,
            date="2026-08-05",
            description="Coffee",
        )

        Expense.objects.create(
            user=self.user,
            title="Обед",
            amount="2500.00",
            category=self.category,
            date="2026-08-15",
            description="Lunch",
        )

        response = self.client.get(
            f"/api/v1/budgets/{budget.id}/progress/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["budget_amount"],
            "15000.00",
        )

        self.assertEqual(
            response.data["spent_amount"],
            "3000.00",
        )

        self.assertEqual(
            response.data["remaining_amount"],
            "12000.00",
        )

        self.assertEqual(
            response.data["percentage_used"],
            20.0,
        )

        self.assertFalse(
            response.data["is_exceeded"],
        )

    def test_budget_progress_is_exceeded(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Большая покупка",
            amount="12000.00",
            category=self.category,
            date="2026-08-10",
            description="Shopping",
        )

        response = self.client.get(
            f"/api/v1/budgets/{budget.id}/progress/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["spent_amount"],
            "12000.00",
        )

        self.assertEqual(
            response.data["remaining_amount"],
            "-2000.00",
        )

        self.assertEqual(
            response.data["percentage_used"],
            120.0,
        )

        self.assertTrue(
            response.data["is_exceeded"],
        )

    def test_budget_progress_contains_only_own_expenses(self):
        second_user = User.objects.create_user(
            username="seconduser",
            password="testpass123",
        )

        second_category = Category.objects.create(
            user=second_user,
            name="Транспорт",
        )

        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Мой кофе",
            amount="2000.00",
            category=self.category,
            date="2026-08-10",
            description="Coffee",
        )

        Expense.objects.create(
            user=second_user,
            title="Чужой расход",
            amount="8000.00",
            category=second_category,
            date="2026-08-10",
            description="Bus",
        )

        response = self.client.get(
            f"/api/v1/budgets/{budget.id}/progress/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["spent_amount"],
            "2000.00",
        )

    def test_budget_progress_respects_budget_month(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Август",
            amount="3000.00",
            category=self.category,
            date="2026-08-10",
            description="August",
        )

        Expense.objects.create(
            user=self.user,
            title="Июль",
            amount="7000.00",
            category=self.category,
            date="2026-07-10",
            description="July",
        )

        response = self.client.get(
            f"/api/v1/budgets/{budget.id}/progress/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["spent_amount"],
            "3000.00",
        )

        self.assertEqual(
            response.data["remaining_amount"],
            "7000.00",
        )

        self.assertEqual(
            response.data["percentage_used"],
            30.0,
        )

    def test_check_budget_exceeded(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Большая покупка",
            amount="12000.00",
            category=self.category,
            date="2026-08-10",
            description="Shopping",
        )

        result = check_budget_exceeded(
            budget.id,
        )

        self.assertEqual(
            result["status"],
            "exceeded",
        )

        self.assertEqual(
            result["budget_amount"],
            "10000.00",
        )

        self.assertEqual(
            result["spent_amount"],
            "12000.00",
        )

    def test_check_budget_not_exceeded(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Кофе",
            amount="2000.00",
            category=self.category,
            date="2026-08-10",
            description="Coffee",
        )

        result = check_budget_exceeded(
            budget.id,
        )

        self.assertEqual(
            result["status"],
            "within_limit",
        )

        self.assertEqual(
            result["budget_amount"],
            "10000.00",
        )

        self.assertEqual(
            result["spent_amount"],
            "2000.00",
        )

    def test_check_budget_exceeded_ignores_other_users_expenses(self):
        second_user = User.objects.create_user(
            username="seconduser",
            password="testpass123",
        )

        second_category = Category.objects.create(
            user=second_user,
            name="Транспорт",
        )

        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Мой расход",
            amount="2000.00",
            category=self.category,
            date="2026-08-10",
            description="My expense",
        )

        Expense.objects.create(
            user=second_user,
            title="Чужой расход",
            amount="20000.00",
            category=second_category,
            date="2026-08-10",
            description="Other user",
        )

        result = check_budget_exceeded(
            budget.id,
        )

        self.assertEqual(
            result["status"],
            "within_limit",
        )

        self.assertEqual(
            result["spent_amount"],
            "2000.00",
        )

    def test_check_budget_exceeded_respects_budget_month(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Август",
            amount="3000.00",
            category=self.category,
            date="2026-08-10",
            description="August",
        )

        Expense.objects.create(
            user=self.user,
            title="Июль",
            amount="20000.00",
            category=self.category,
            date="2026-07-10",
            description="July",
        )

        result = check_budget_exceeded(
            budget.id,
        )

        self.assertEqual(
            result["status"],
            "within_limit",
        )

        self.assertEqual(
            result["spent_amount"],
            "3000.00",
        )

    def test_check_budget_exceeded_budget_not_found(self):
        result = check_budget_exceeded(
            999999,
        )

        self.assertEqual(
            result,
            "Budget 999999 not found",
        )

    def test_check_budget_exceeded_creates_notification(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Большая покупка",
            amount="12000.00",
            category=self.category,
            date="2026-08-10",
            description="Shopping",
        )

        result = check_budget_exceeded(
            budget.id,
        )

        self.assertEqual(
            result["status"],
            "exceeded",
        )

        self.assertTrue(
            result["notification_created"],
        )

        self.assertEqual(
            Notification.objects.count(),
            1,
        )

        notification = Notification.objects.first()

        self.assertEqual(
            notification.user,
            self.user,
        )

        self.assertEqual(
            notification.budget,
            budget,
        )

        self.assertEqual(
            notification.notification_type,
            Notification.NotificationType.BUDGET_EXCEEDED,
        )

    def test_check_budget_exceeded_does_not_create_duplicate_notification(
        self,
    ):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Большая покупка",
            amount="12000.00",
            category=self.category,
            date="2026-08-10",
            description="Shopping",
        )

        first_result = check_budget_exceeded(
            budget.id,
        )

        second_result = check_budget_exceeded(
            budget.id,
        )

        self.assertTrue(
            first_result["notification_created"],
        )

        self.assertFalse(
            second_result["notification_created"],
        )

        self.assertEqual(
            Notification.objects.count(),
            1,
        )

    def test_check_budget_not_exceeded_does_not_create_notification(
        self,
    ):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount="10000.00",
            month="2026-08-01",
        )

        Expense.objects.create(
            user=self.user,
            title="Кофе",
            amount="2000.00",
            category=self.category,
            date="2026-08-10",
            description="Coffee",
        )

        result = check_budget_exceeded(
            budget.id,
        )

        self.assertEqual(
            result["status"],
            "within_limit",
        )

        self.assertEqual(
            Notification.objects.count(),
            0,
        )
