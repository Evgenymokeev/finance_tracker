from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from django.contrib.auth.models import User

from categories.models import Category
from expenses.models import Expense
from goals.models import FinancialGoal


@pytest.mark.django_db
class TestGoalsAnalyticsView:

    def setup_method(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="testpassword123",
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Еда",
        )

        self.other_category = Category.objects.create(
            user=self.other_user,
            name="Еда",
        )

        self.url = "/api/v1/analytics/goals/"

    def test_own_goals_are_returned(self):
        self.client.force_authenticate(
            user=self.user
        )

        goal = FinancialGoal.objects.create(
            user=self.user,
            title="MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("20000.00"),
            deadline=date(2027, 1, 1),
        )

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert len(response.data["goals"]) == 1
        assert response.data["goals"][0]["goal"] == "MacBook"

    def test_spent_amount_is_calculated(self):
        self.client.force_authenticate(
            user=self.user
        )

        goal = FinancialGoal.objects.create(
            user=self.user,
            title="MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("20000.00"),
            deadline=date(2027, 1, 1),
        )

        Expense.objects.create(
            user=self.user,
            title="MacBook accessories",
            amount=Decimal("2500.00"),
            category=self.category,
            goal=goal,
            date=date.today(),
        )

        Expense.objects.create(
            user=self.user,
            title="Another expense",
            amount=Decimal("1500.00"),
            category=self.category,
            goal=goal,
            date=date.today(),
        )

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.data["goals"][0]["spent_amount"] == "4000.00"

    def test_goal_without_expenses_has_zero_spent_amount(self):
        self.client.force_authenticate(
            user=self.user
        )

        FinancialGoal.objects.create(
            user=self.user,
            title="Vacation",
            target_amount=Decimal("30000.00"),
            current_amount=Decimal("10000.00"),
            deadline=date(2027, 1, 1),
        )

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.data["goals"][0]["spent_amount"] == "0.00"

    def test_expenses_without_goal_are_not_counted(self):
        self.client.force_authenticate(
            user=self.user
        )

        goal = FinancialGoal.objects.create(
            user=self.user,
            title="MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("20000.00"),
            deadline=date(2027, 1, 1),
        )

        Expense.objects.create(
            user=self.user,
            title="Goal expense",
            amount=Decimal("2500.00"),
            category=self.category,
            goal=goal,
            date=date.today(),
        )

        Expense.objects.create(
            user=self.user,
            title="Normal expense",
            amount=Decimal("5000.00"),
            category=self.category,
            goal=None,
            date=date.today(),
        )

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.data["goals"][0]["spent_amount"] == "2500.00"

    def test_other_users_goals_are_not_visible(self):
        self.client.force_authenticate(
            user=self.user
        )

        FinancialGoal.objects.create(
            user=self.user,
            title="My goal",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("10000.00"),
            deadline=date(2027, 1, 1),
        )

        FinancialGoal.objects.create(
            user=self.other_user,
            title="Other goal",
            target_amount=Decimal("100000.00"),
            current_amount=Decimal("50000.00"),
            deadline=date(2027, 1, 1),
        )

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert len(response.data["goals"]) == 1
        assert response.data["goals"][0]["goal"] == "My goal"

    def test_remaining_amount_is_correct(self):
        self.client.force_authenticate(
            user=self.user
        )

        FinancialGoal.objects.create(
            user=self.user,
            title="MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("20000.00"),
            deadline=date(2027, 1, 1),
        )

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.data["goals"][0]["remaining_amount"] == "30000.00"

    def test_progress_percent_is_correct(self):
        self.client.force_authenticate(
            user=self.user
        )

        FinancialGoal.objects.create(
            user=self.user,
            title="MacBook",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("20000.00"),
            deadline=date(2027, 1, 1),
        )

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.data["goals"][0]["progress_percent"] == 40.0

    def test_unauthenticated_user_gets_401(self):
        response = self.client.get(self.url)

        assert response.status_code == 401