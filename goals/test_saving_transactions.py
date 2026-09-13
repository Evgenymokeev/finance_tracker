import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from goals.models import (
    FinancialGoal,
    GoalAutomaticSaving,
    GoalSavingTransaction,
)


@pytest.mark.django_db
def test_create_saving_transaction():
    user = User.objects.create_user(
        username="transaction_user",
        password="password123",
    )

    goal = FinancialGoal.objects.create(
        user=user,
        title="Laptop",
        target_amount="1000.00",
        current_amount="0.00",
    )

    transaction = GoalSavingTransaction.objects.create(
        goal=goal,
        amount="100.00",
    )

    assert transaction.goal == goal
    assert transaction.amount == "100.00"
    assert (
        transaction.transaction_type
        == GoalSavingTransaction.TransactionType.DEPOSIT
    )
    assert (
        transaction.source
        == GoalSavingTransaction.Source.MANUAL
    )
    assert transaction.created_at is not None


@pytest.mark.django_db
def test_saving_transaction_str():
    user = User.objects.create_user(
        username="transaction_str_user",
        password="password123",
    )

    goal = FinancialGoal.objects.create(
        user=user,
        title="Emergency Fund",
        target_amount="2000.00",
    )

    transaction = GoalSavingTransaction.objects.create(
        goal=goal,
        amount="250.00",
    )

    assert str(transaction) == "Emergency Fund: 250.00"


@pytest.mark.django_db
def test_saving_transaction_belongs_to_goal():
    user = User.objects.create_user(
        username="transaction_goal_user",
        password="password123",
    )

    goal = FinancialGoal.objects.create(
        user=user,
        title="Vacation",
        target_amount="1500.00",
    )

    GoalSavingTransaction.objects.create(
        goal=goal,
        amount="100.00",
    )

    GoalSavingTransaction.objects.create(
        goal=goal,
        amount="200.00",
    )

    assert goal.saving_transactions.count() == 2


@pytest.mark.django_db
def test_saving_transaction_can_be_linked_to_automatic_saving():
    user = User.objects.create_user(
        username="transaction_auto_user",
        password="password123",
    )

    goal = FinancialGoal.objects.create(
        user=user,
        title="New Phone",
        target_amount="800.00",
    )

    automatic_saving = GoalAutomaticSaving.objects.create(
        goal=goal,
        amount="100.00",
        frequency=GoalAutomaticSaving.Frequency.DAILY,
        next_run_at=timezone.now(),
    )

    transaction = GoalSavingTransaction.objects.create(
        goal=goal,
        automatic_saving=automatic_saving,
        amount="100.00",
        source=GoalSavingTransaction.Source.AUTOMATIC,
    )

    assert transaction.automatic_saving == automatic_saving
    assert (
        transaction.source
        == GoalSavingTransaction.Source.AUTOMATIC
    )
    assert automatic_saving.transactions.count() == 1


@pytest.mark.django_db
def test_deleting_goal_deletes_saving_transactions():
    user = User.objects.create_user(
        username="transaction_delete_goal_user",
        password="password123",
    )

    goal = FinancialGoal.objects.create(
        user=user,
        title="Car",
        target_amount="5000.00",
    )

    transaction = GoalSavingTransaction.objects.create(
        goal=goal,
        amount="500.00",
    )

    transaction_id = transaction.id

    goal.delete()

    assert not GoalSavingTransaction.objects.filter(
        id=transaction_id
    ).exists()


@pytest.mark.django_db
def test_deleting_automatic_saving_keeps_transaction():
    user = User.objects.create_user(
        username="transaction_delete_auto_user",
        password="password123",
    )

    goal = FinancialGoal.objects.create(
        user=user,
        title="Computer",
        target_amount="2000.00",
    )

    automatic_saving = GoalAutomaticSaving.objects.create(
        goal=goal,
        amount="100.00",
        frequency=GoalAutomaticSaving.Frequency.WEEKLY,
        next_run_at=timezone.now(),
    )

    transaction = GoalSavingTransaction.objects.create(
        goal=goal,
        automatic_saving=automatic_saving,
        amount="100.00",
        source=GoalSavingTransaction.Source.AUTOMATIC,
    )

    transaction_id = transaction.id

    automatic_saving.delete()

    transaction.refresh_from_db()

    assert transaction.id == transaction_id
    assert transaction.automatic_saving is None