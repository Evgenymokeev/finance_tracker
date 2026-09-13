from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from goals.models import (
    FinancialGoal,
    GoalAutomaticSaving,
    GoalSavingTransaction,
)
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

    def test_automatic_saving_creates_transaction(self):
        """
        Проверяем основной сценарий Automatic Saving.

        Когда Celery обрабатывает активное расписание, оно должно:

        1. создать GoalSavingTransaction;
        2. указать правильную сумму;
        3. указать источник automatic;
        4. связать транзакцию с конкретным Automatic Saving;
        5. увеличить current_amount цели.
        """

        # Создаём пользователя, которому принадлежит финансовая цель.
        user = User.objects.create_user(
            username="task_transaction_user",
            password="password123",
        )

        # Создаём активную цель.
        # До автоматического пополнения на ней находится 200 из 1000.
        goal = FinancialGoal.objects.create(
            user=user,
            title="Transaction Goal",
            target_amount="1000.00",
            current_amount="200.00",
            status=FinancialGoal.Status.ACTIVE,
        )

        # Создаём Automatic Saving на 100.
        # next_run_at устанавливаем в прошлое,
        # чтобы задача считала расписание готовым к обработке.
        automatic_saving = GoalAutomaticSaving.objects.create(
            goal=goal,
            amount="100.00",
            frequency=GoalAutomaticSaving.Frequency.DAILY,
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        # Запускаем Celery task напрямую в тесте.
        # Это позволяет проверить бизнес-логику задачи
        # без необходимости реально ждать Celery Beat.
        result = process_automatic_savings()

        # После выполнения задачи должна появиться
        # одна транзакция для нашей цели.
        transaction = GoalSavingTransaction.objects.get(
            goal=goal,
        )

        # Проверяем результат самой Celery-задачи.
        self.assertEqual(
            result,
            {"processed": 1},
        )

        # В историю должна попасть именно сумма Automatic Saving.
        self.assertEqual(
            transaction.amount,
            Decimal("100.00"),
        )

        # Automatic Saving создаёт именно пополнение.
        self.assertEqual(
            transaction.transaction_type,
            GoalSavingTransaction.TransactionType.DEPOSIT,
        )

        # Источник операции должен быть automatic,
        # а не manual.
        self.assertEqual(
            transaction.source,
            GoalSavingTransaction.Source.AUTOMATIC,
        )

        # Проверяем связь транзакции
        # с конкретным расписанием.
        self.assertEqual(
            transaction.automatic_saving,
            automatic_saving,
        )

        # Получаем актуальное состояние цели из базы.
        # Без refresh_from_db() объект goal всё ещё может содержать
        # старое значение current_amount в памяти.
        goal.refresh_from_db()

        # 200 + 100 = 300.
        self.assertEqual(
            goal.current_amount,
            Decimal("300.00"),
        )

    def test_automatic_saving_transaction_is_limited_by_remaining_amount(
        self,
    ):
        """
        Проверяем важный сценарий достижения цели.

        Если Automatic Saving должен добавить больше денег,
        чем осталось до target_amount, мы не должны записывать
        лишнюю сумму.

        Например:

            current_amount = 250
            target_amount = 300
            automatic_saving = 100

        Фактически можно добавить только 50.

        Поэтому Transaction должна быть на 50,
        а не на 100.
        """

        # Создаём пользователя.
        user = User.objects.create_user(
            username="task_transaction_limit_user",
            password="password123",
        )

        # До цели осталось только 50.
        goal = FinancialGoal.objects.create(
            user=user,
            title="Limited Transaction Goal",
            target_amount="300.00",
            current_amount="250.00",
            status=FinancialGoal.Status.ACTIVE,
        )

        # Automatic Saving пытается добавить 100.
        # Но цель позволяет добавить только оставшиеся 50.
        automatic_saving = GoalAutomaticSaving.objects.create(
            goal=goal,
            amount="100.00",
            frequency=GoalAutomaticSaving.Frequency.DAILY,
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        # Обрабатываем Automatic Saving.
        result = process_automatic_savings()

        # Получаем созданную транзакцию.
        transaction = GoalSavingTransaction.objects.get(
            goal=goal,
        )

        # Обновляем объекты из базы после выполнения task.
        goal.refresh_from_db()
        automatic_saving.refresh_from_db()

        # Одна автоматическая операция должна быть обработана.
        self.assertEqual(
            result,
            {"processed": 1},
        )

        # Очень важная проверка:
        # в историю попадает только реально зачисленные 50.
        self.assertEqual(
            transaction.amount,
            Decimal("50.00"),
        )

        # После пополнения цель должна быть ровно 300.
        self.assertEqual(
            goal.current_amount,
            Decimal("300.00"),
        )

        # Цель достигнута, поэтому её статус
        # меняется на completed.
        self.assertEqual(
            goal.status,
            FinancialGoal.Status.COMPLETED,
        )

        # После достижения цели Automatic Saving
        # больше не должен выполняться.
        self.assertFalse(
            automatic_saving.is_active,
        )

    def test_automatic_saving_transaction_is_created_atomically(self):
        """
        Проверяем согласованность изменения цели и создания транзакции.

        В production это важно, потому что нам нельзя получить ситуацию,
        когда:

            Transaction создана,
            но current_amount не обновился

        или наоборот.

        Вся операция выполняется внутри transaction.atomic().
        """

        # Создаём пользователя.
        user = User.objects.create_user(
            username="task_transaction_atomic_user",
            password="password123",
        )

        # Создаём активную цель.
        goal = FinancialGoal.objects.create(
            user=user,
            title="Atomic Goal",
            target_amount="1000.00",
            current_amount="200.00",
            status=FinancialGoal.Status.ACTIVE,
        )

        # Создаём готовое к выполнению Automatic Saving.
        automatic_saving = GoalAutomaticSaving.objects.create(
            goal=goal,
            amount="100.00",
            frequency=GoalAutomaticSaving.Frequency.DAILY,
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        # Запускаем обработку.
        result = process_automatic_savings()

        # Проверяем, что Automatic Saving действительно обработан.
        self.assertEqual(
            result,
            {"processed": 1},
        )

        # Должна существовать ровно одна транзакция,
        # созданная именно этим Automatic Saving.
        self.assertEqual(
            GoalSavingTransaction.objects.filter(
                goal=goal,
                automatic_saving=automatic_saving,
            ).count(),
            1,
        )

        # Проверяем итоговое состояние цели.
        goal.refresh_from_db()

        # Баланс должен быть обновлён вместе
        # с созданием транзакции.
        self.assertEqual(
            goal.current_amount,
            Decimal("300.00"),
        )