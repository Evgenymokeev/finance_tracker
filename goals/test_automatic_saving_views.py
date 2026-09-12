from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import FinancialGoal, GoalAutomaticSaving


class GoalAutomaticSavingViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="password123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="password123",
        )

        self.goal = FinancialGoal.objects.create(
            user=self.user,
            title="New Laptop",
            target_amount=Decimal("2000.00"),
        )

        self.other_goal = FinancialGoal.objects.create(
            user=self.other_user,
            title="Other Goal",
            target_amount=Decimal("1000.00"),
        )

        self.url = (
            f"/api/v1/goals/{self.goal.id}/automatic-saving/"
        )

        self.client.force_authenticate(user=self.user)

    def test_create_automatic_saving(self):
        response = self.client.post(
            self.url,
            {
                "amount": "100.00",
                "frequency": "weekly",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(response.data["amount"], "100.00")
        self.assertEqual(response.data["frequency"], "weekly")
        self.assertTrue(response.data["is_active"])
        self.assertIsNotNone(response.data["next_run_at"])

        self.assertTrue(
            GoalAutomaticSaving.objects.filter(
                goal=self.goal,
            ).exists()
        )

    def test_create_custom_automatic_saving(self):
        response = self.client.post(
            self.url,
            {
                "amount": "50.00",
                "frequency": "custom",
                "interval": 14,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(response.data["frequency"], "custom")
        self.assertEqual(response.data["interval"], 14)

    def test_next_run_at_is_calculated_by_server(self):
        before = timezone.now()

        response = self.client.post(
            self.url,
            {
                "amount": "100.00",
                "frequency": "daily",
            },
            format="json",
        )

        after = timezone.now()

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        next_run_at = response.data["next_run_at"]

        self.assertIsNotNone(next_run_at)

        automatic_saving = GoalAutomaticSaving.objects.get(
            goal=self.goal,
        )

        self.assertGreater(
            automatic_saving.next_run_at,
            before + timedelta(hours=23),
        )

        self.assertLess(
            automatic_saving.next_run_at,
            after + timedelta(hours=25),
        )

    def test_next_run_at_cannot_be_set_by_client(self):
        response = self.client.post(
            self.url,
            {
                "amount": "100.00",
                "frequency": "daily",
                "next_run_at": "2030-01-01T12:00:00Z",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        automatic_saving = GoalAutomaticSaving.objects.get(
            goal=self.goal,
        )

        self.assertLess(
            automatic_saving.next_run_at,
            timezone.now() + timedelta(days=2),
        )

    def test_get_automatic_saving(self):
        automatic_saving = GoalAutomaticSaving.objects.create(
            goal=self.goal,
            amount=Decimal("100.00"),
            frequency="weekly",
            next_run_at=timezone.now() + timedelta(days=7),
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            automatic_saving.id,
        )

    def test_get_returns_404_when_automatic_saving_does_not_exist(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_create_duplicate_automatic_saving_is_rejected(self):
        GoalAutomaticSaving.objects.create(
            goal=self.goal,
            amount=Decimal("100.00"),
            frequency="weekly",
            next_run_at=timezone.now() + timedelta(days=7),
        )

        response = self.client.post(
            self.url,
            {
                "amount": "200.00",
                "frequency": "daily",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_update_amount(self):
        automatic_saving = GoalAutomaticSaving.objects.create(
            goal=self.goal,
            amount=Decimal("100.00"),
            frequency="weekly",
            next_run_at=timezone.now() + timedelta(days=7),
        )

        response = self.client.patch(
            self.url,
            {
                "amount": "150.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        automatic_saving.refresh_from_db()

        self.assertEqual(
            automatic_saving.amount,
            Decimal("150.00"),
        )

    def test_update_frequency_recalculates_next_run_at(self):
        automatic_saving = GoalAutomaticSaving.objects.create(
            goal=self.goal,
            amount=Decimal("100.00"),
            frequency="weekly",
            next_run_at=timezone.now() + timedelta(days=7),
        )

        response = self.client.patch(
            self.url,
            {
                "frequency": "daily",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        automatic_saving.refresh_from_db()

        self.assertEqual(
            automatic_saving.frequency,
            "daily",
        )

        self.assertLess(
            automatic_saving.next_run_at,
            timezone.now() + timedelta(days=2),
        )

    def test_delete_automatic_saving(self):
        GoalAutomaticSaving.objects.create(
            goal=self.goal,
            amount=Decimal("100.00"),
            frequency="weekly",
            next_run_at=timezone.now() + timedelta(days=7),
        )

        response = self.client.delete(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            GoalAutomaticSaving.objects.filter(
                goal=self.goal,
            ).exists()
        )

    def test_cannot_access_another_users_goal(self):
        other_url = (
            f"/api/v1/goals/{self.other_goal.id}/"
            "automatic-saving/"
        )

        response = self.client.post(
            other_url,
            {
                "amount": "100.00",
                "frequency": "weekly",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )