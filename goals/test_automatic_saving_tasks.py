from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import FinancialGoal, GoalAutomaticSaving
from .tasks import process_automatic_savings


class AutomaticSavingTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="password123",
        )

        self.goal = FinancialGoal.objects.create(
            user=self.user,
            title="New Laptop",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("300.00"),
        )

    def create_automatic_saving(
        self,
        amount="100.00",
        frequency="weekly",
        next_run_at=None,
        is_active=True,
        interval=None,
    ):
        if next_run_at is None:
            next_run_at = timezone.now() - timedelta(minutes=1)

        return GoalAutomaticSaving.objects.create(
            goal=self.goal,
            amount=Decimal(amount),
            frequency=frequency,
            interval=interval,
            next_run_at=next_run_at,
            is_active=is_active,
        )

    def test_process_due_automatic_saving(self):
        """
        Проверяем основную работу задачи.

        Если next_run_at уже наступил,
        сумма должна быть добавлена к цели.
        """
        automatic_saving = self.create_automatic_saving()

        result = process_automatic_savings()

        self.goal.refresh_from_db()
        automatic_saving.refresh_from_db()

        self.assertEqual(result["processed"], 1)

        self.assertEqual(
            self.goal.current_amount,
            Decimal("400.00"),
        )

        self.assertIsNotNone(
            automatic_saving.last_run_at,
        )

        self.assertGreater(
            automatic_saving.next_run_at,
            timezone.now(),
        )

    def test_future_automatic_saving_is_not_processed(self):
        """
        Если next_run_at находится в будущем,
        автоматическое пополнение выполнять нельзя.
        """
        automatic_saving = self.create_automatic_saving(
            next_run_at=timezone.now() + timedelta(days=1),
        )

        result = process_automatic_savings()

        self.goal.refresh_from_db()
        automatic_saving.refresh_from_db()

        self.assertEqual(result["processed"], 0)

        self.assertEqual(
            self.goal.current_amount,
            Decimal("300.00"),
        )

        self.assertIsNone(
            automatic_saving.last_run_at,
        )

    def test_inactive_automatic_saving_is_not_processed(self):
        """
        Неактивное автоматическое пополнение
        не должно обрабатываться.
        """
        automatic_saving = self.create_automatic_saving(
            is_active=False,
        )

        result = process_automatic_savings()

        self.goal.refresh_from_db()
        automatic_saving.refresh_from_db()

        self.assertEqual(result["processed"], 0)

        self.assertEqual(
            self.goal.current_amount,
            Decimal("300.00"),
        )

        self.assertIsNone(
            automatic_saving.last_run_at,
        )

    def test_completed_goal_is_not_processed(self):
        """
        Если цель уже completed,
        автоматические пополнения больше не выполняются.
        """
        self.goal.status = FinancialGoal.Status.COMPLETED
        self.goal.save()

        automatic_saving = self.create_automatic_saving()

        result = process_automatic_savings()

        self.goal.refresh_from_db()
        automatic_saving.refresh_from_db()

        self.assertEqual(result["processed"], 0)

        self.assertEqual(
            self.goal.current_amount,
            Decimal("300.00"),
        )

        self.assertIsNone(
            automatic_saving.last_run_at,
        )

    def test_automatic_saving_completes_goal(self):
        """
        Если очередной взнос достигает цели,
        current_amount не должен превысить target_amount.

        Цель переводится в completed,
        а automatic saving отключается.
        """
        automatic_saving = self.create_automatic_saving(
            amount="800.00",
        )

        result = process_automatic_savings()

        self.goal.refresh_from_db()
        automatic_saving.refresh_from_db()

        self.assertEqual(result["processed"], 1)

        self.assertEqual(
            self.goal.current_amount,
            Decimal("1000.00"),
        )

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.COMPLETED,
        )

        self.assertFalse(
            automatic_saving.is_active,
        )

        self.assertIsNotNone(
            automatic_saving.last_run_at,
        )

    def test_amount_never_exceeds_target_amount(self):
        """
        Проверяем ситуацию, когда до цели осталось меньше,
        чем размер автоматического взноса.

        Например:

        target = 1000
        current = 950
        saving = 100

        Результат должен быть 1000, а не 1050.
        """
        self.goal.current_amount = Decimal("950.00")
        self.goal.save()

        automatic_saving = self.create_automatic_saving(
            amount="100.00",
        )

        process_automatic_savings()

        self.goal.refresh_from_db()
        automatic_saving.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("1000.00"),
        )

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.COMPLETED,
        )

        self.assertFalse(
            automatic_saving.is_active,
        )

    def test_next_run_at_is_recalculated_for_weekly_frequency(self):
        """
        После выполнения weekly-взноса
        следующий запуск должен быть перенесён примерно
        на 7 дней вперёд.
        """
        automatic_saving = self.create_automatic_saving(
            frequency="weekly",
        )

        old_next_run_at = automatic_saving.next_run_at

        process_automatic_savings()

        automatic_saving.refresh_from_db()

        self.assertGreater(
            automatic_saving.next_run_at,
            old_next_run_at,
        )

        expected_minimum = timezone.now() + timedelta(days=6)

        self.assertGreater(
            automatic_saving.next_run_at,
            expected_minimum,
        )

    def test_custom_frequency_uses_interval(self):
        """
        Для custom frequency используется interval.

        Например interval=14 означает,
        что следующий запуск будет примерно через 14 дней.
        """
        automatic_saving = self.create_automatic_saving(
            frequency="custom",
            interval=14,
        )

        process_automatic_savings()

        automatic_saving.refresh_from_db()

        expected_minimum = timezone.now() + timedelta(days=13)

        self.assertGreater(
            automatic_saving.next_run_at,
            expected_minimum,
        )

    def test_task_does_not_process_same_saving_twice(self):
        """
        После первого запуска next_run_at переносится в будущее.

        Поэтому повторный запуск Celery не должен
        сделать второй взнос сразу же.
        """
        automatic_saving = self.create_automatic_saving()

        process_automatic_savings()

        self.goal.refresh_from_db()
        automatic_saving.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("400.00"),
        )

        process_automatic_savings()

        self.goal.refresh_from_db()
        automatic_saving.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("400.00"),
        )