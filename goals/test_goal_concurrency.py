
"""
Конкурентные тесты финансовых целей.

Проверяют корректность изменения баланса при одновременных
запросах к API с использованием PostgreSQL row-level locks.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient

from .models import (
    FinancialGoal,
    GoalAutomaticSaving,
    GoalSavingTransaction,
)
from .tasks import process_automatic_savings

@skipUnless(
    connection.vendor == "postgresql",
    "Concurrency tests require PostgreSQL.",
)
class FinancialGoalConcurrencyTests(TransactionTestCase):
    """
    Проверяет конкурентные операции над одной финансовой целью.

    TransactionTestCase позволяет выполнять независимые транзакции
    в отдельных потоках. Это необходимо для проверки select_for_update().
    """

    reset_sequences = True

    def setUp(self):
        self.user = User.objects.create_user(
            username="concurrency_user",
            password="testpassword123",
        )

        self.goal = FinancialGoal.objects.create(
            user=self.user,
            title="Concurrency test goal",
            target_amount=Decimal("50000.00"),
            current_amount=Decimal("10000.00"),
        )

        self.deposit_url = (
            f"/api/v1/goals/{self.goal.id}/deposit/"
        )

    def _make_deposit(self, barrier, amount):
        """
        Выполняет API-запрос в отдельном потоке.

        Каждый поток получает собственное соединение с БД.
        Barrier синхронизирует начало запросов.
        """

        close_old_connections()

        try:
            client = APIClient()
            client.force_authenticate(user=self.user)

            # Оба потока начинают запросы одновременно.
            barrier.wait(timeout=15)

            response = client.post(
                self.deposit_url,
                {"amount": str(amount)},
                format="json",
            )

            return response.status_code

        finally:
            close_old_connections()

    def test_concurrent_deposits_do_not_exceed_goal_target(self):
        """
        Проверяет два одновременных пополнения одной цели.

        Начальные условия:
        - target_amount = 50000;
        - current_amount = 10000;
        - два запроса по 30000.

        Ожидаемый результат:
        - оба запроса успешно обработаны;
        - итоговый баланс равен 50000;
        - цель имеет статус COMPLETED;
        - созданы две транзакции;
        - сумма транзакций равна 40000;
        - ни одна транзакция не превышает фактически доступный остаток.
        """

        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    self._make_deposit,
                    barrier,
                    Decimal("30000.00"),
                )
                for _ in range(2)
            ]

            response_statuses = [
                future.result(timeout=30)
                for future in futures
            ]

        # Оба запроса должны успешно завершиться.
        self.assertEqual(
            response_statuses,
            [status.HTTP_200_OK, status.HTTP_200_OK],
        )

        self.goal.refresh_from_db()

        # Баланс не должен превышать целевую сумму.
        self.assertEqual(
            self.goal.current_amount,
            Decimal("50000.00"),
        )

        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.COMPLETED,
        )

        transactions = GoalSavingTransaction.objects.filter(
            goal=self.goal,
            transaction_type=(
                GoalSavingTransaction.TransactionType.DEPOSIT
            ),
            source=GoalSavingTransaction.Source.MANUAL,
        )

        # Должны сохраниться обе операции.
        self.assertEqual(
            transactions.count(),
            2,
        )

        transaction_amounts = sorted(
            transactions.values_list("amount", flat=True)
        )

        # Один запрос зачисляет 30000, второй — оставшиеся 10000.
        self.assertEqual(
            transaction_amounts,
            [
                Decimal("10000.00"),
                Decimal("30000.00"),
            ],
        )

        # Общая сумма фактически зачисленных средств.
        self.assertEqual(
            sum(transaction_amounts),
            Decimal("40000.00"),
        )

    def _make_withdraw(self, barrier, amount):
        """
        Выполняет запрос на снятие средств в отдельном потоке.

        Каждый поток использует собственное соединение с БД.
        """

        close_old_connections()

        try:
            client = APIClient()
            client.force_authenticate(user=self.user)

            barrier.wait(timeout=15)

            response = client.post(
                f"/api/v1/goals/{self.goal.id}/withdraw/",
                {"amount": str(amount)},
                format="json",
            )

            return response.status_code

        finally:
            close_old_connections()

    def test_concurrent_withdrawals_do_not_exceed_goal_balance(self):
        """
        Проверяет два одновременных снятия средств с одной цели.

        Начальные условия:
        - current_amount = 10000;
        - два запроса по 7000.

        Ожидаемый результат:
        - один запрос получает HTTP 200;
        - второй получает HTTP 400;
        - баланс равен 3000;
        - создана только одна транзакция снятия;
        - баланс не становится отрицательным.
        """

        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    self._make_withdraw,
                    barrier,
                    Decimal("7000.00"),
                )
                for _ in range(2)
            ]

            response_statuses = [
                future.result(timeout=30)
                for future in futures
            ]

        self.assertEqual(
            sorted(response_statuses),
            [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
            ],
        )

        self.goal.refresh_from_db()

        self.assertEqual(
            self.goal.current_amount,
            Decimal("3000.00"),
        )

        self.assertGreaterEqual(
            self.goal.current_amount,
            Decimal("0.00"),
        )

        transactions = GoalSavingTransaction.objects.filter(
            goal=self.goal,
            transaction_type=(
                GoalSavingTransaction.TransactionType.WITHDRAWAL
            ),
            source=GoalSavingTransaction.Source.MANUAL,
        )

        self.assertEqual(
            transactions.count(),
            1,
        )

        transaction = transactions.get()

        self.assertEqual(
            transaction.amount,
            Decimal("7000.00"),
        )

    def _process_automatic_saving(self, barrier):
        """
        Выполняет Automatic Saving в отдельном потоке.

        Закрываем старые соединения, чтобы поток получил
        собственное соединение с PostgreSQL.

        Barrier позволяет синхронизировать запуск Celery task
        с ручным пополнением через API.
        """

        close_old_connections()

        try:
            barrier.wait(timeout=15)

            return process_automatic_savings()

        finally:
            close_old_connections()

    def test_concurrent_manual_and_automatic_deposits_do_not_exceed_target(
        self,
    ):
        """
        Проверяем конкурентную работу двух механизмов пополнения:

        1. Ручное пополнение через API.
        2. Автоматическое пополнение через Celery task.

        Обе операции пытаются добавить 30 000 к цели,
        у которой осталось только 40 000.

        Независимо от порядка выполнения операций итоговый баланс
        не должен превышать target_amount.
        """

        # Создаём активное расписание Automatic Saving.
        # Оно должно быть готово к выполнению.
        automatic_saving = GoalAutomaticSaving.objects.create(
            goal=self.goal,
            amount=Decimal("30000.00"),
            frequency=GoalAutomaticSaving.Frequency.DAILY,
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        # Синхронизируем начало двух конкурентных операций.
        barrier = Barrier(2)

        # Один поток выполняет ручное пополнение через API,
        # второй запускает обработку Automatic Saving.
        with ThreadPoolExecutor(max_workers=2) as executor:
            manual_future = executor.submit(
                self._make_deposit,
                barrier,
                Decimal("30000.00"),
            )

            automatic_future = executor.submit(
                self._process_automatic_saving,
                barrier,
            )

            manual_status = manual_future.result(timeout=30)
            automatic_result = automatic_future.result(timeout=30)

        # Получаем актуальное состояние цели из PostgreSQL.
        self.goal.refresh_from_db()
        automatic_saving.refresh_from_db()

        # Цель должна быть заполнена ровно до целевой суммы.
        self.assertEqual(
            self.goal.current_amount,
            Decimal("50000.00"),
        )

        # Превышение целевой суммы недопустимо.
        self.assertLessEqual(
            self.goal.current_amount,
            self.goal.target_amount,
        )

        # После достижения цели её статус должен быть completed.
        self.assertEqual(
            self.goal.status,
            FinancialGoal.Status.COMPLETED,
        )

        # Автоматическое расписание должно отключиться.
        self.assertFalse(
            automatic_saving.is_active,
        )

        # Обе операции должны успешно выполниться:
        # одна зачисляет 30000, вторая — оставшиеся 10000.
        self.assertEqual(
            manual_status,
            status.HTTP_200_OK,
        )

        # Automatic Saving должен обработать расписание ровно один раз.
        self.assertEqual(
            automatic_result["processed"],
            1,
        )

        # Получаем историю операций.
        transactions = GoalSavingTransaction.objects.filter(
            goal=self.goal,
        )

        automatic_transactions = transactions.filter(
            source=GoalSavingTransaction.Source.AUTOMATIC,
            automatic_saving=automatic_saving,
            transaction_type=GoalSavingTransaction.TransactionType.DEPOSIT,
        )

        manual_transactions = transactions.filter(
            source=GoalSavingTransaction.Source.MANUAL,
            transaction_type=GoalSavingTransaction.TransactionType.DEPOSIT,
        )

        # Автоматическая транзакция должна существовать ровно одна.
        self.assertEqual(
            automatic_transactions.count(),
            1,
        )

        # Ручная операция должна создать ровно одну транзакцию.
        self.assertEqual(
            manual_transactions.count(),
            1,
        )

        # Сумма всех успешных пополнений должна соответствовать
        # фактически накопленной сумме.
        self.assertEqual(
            sum(
                transactions.values_list("amount", flat=True),
                Decimal("0.00"),
            ),
            Decimal("40000.00"),
        )
