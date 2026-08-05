from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.test import APITestCase

from categories.models import Category
from expenses.models import Expense


class AnalyticsAPITest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Еда"
        )

        self.client.force_authenticate(
            user=self.user
        )


    def test_dashboard_analytics(self):

        Expense.objects.create(
            user=self.user,
            title="Кофе",
            amount="80.00",
            category=self.category,
            date="2026-08-01"
        )

        response = self.client.get(
            "/api/v1/analytics/dashboard/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["total_expenses"],
            "80.00"
        )


    def test_monthly_analytics(self):

        Expense.objects.create(
            user=self.user,
            title="Кофе",
            amount="80.00",
            category=self.category,
            date="2026-08-01"
        )

        response = self.client.get(
            "/api/v1/analytics/monthly/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertTrue(
            len(response.data) > 0
        )

# Create your tests here.
