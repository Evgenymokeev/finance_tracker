from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import (
    FinancialGoal,
    GoalAutomaticSaving,
    GoalSavingTransaction,
)
from .services import calculate_next_run_at


@shared_task
def process_automatic_savings():
    now = timezone.now()

    due_saving_ids = (
        GoalAutomaticSaving.objects
        .filter(
            is_active=True,
            next_run_at__lte=now,
            goal__status=FinancialGoal.Status.ACTIVE,
        )
        .values_list("id", flat=True)
    )

    processed = 0

    for saving_id in due_saving_ids:
        with transaction.atomic():
            # Сначала блокируем цель. Ручные операции будут использовать
            # тот же порядок блокировок, чтобы избежать взаимных блокировок.
            goal_id = (
                GoalAutomaticSaving.objects
                .filter(id=saving_id)
                .values_list("goal_id", flat=True)
                .first()
            )

            if goal_id is None:
                continue

            try:
                goal = (
                    FinancialGoal.objects
                    .select_for_update()
                    .get(id=goal_id)
                )
            except FinancialGoal.DoesNotExist:
                continue

            automatic_saving = (
                GoalAutomaticSaving.objects
                .select_for_update()
                .filter(id=saving_id, goal_id=goal.id)
                .first()
            )

            if automatic_saving is None:
                continue

            if (
                not automatic_saving.is_active
                or automatic_saving.next_run_at > now
                or goal.status != FinancialGoal.Status.ACTIVE
            ):
                continue

            remaining_amount = goal.target_amount - goal.current_amount
            saving_amount = min(
                automatic_saving.amount,
                remaining_amount,
            )

            if saving_amount <= 0:
                continue

            GoalSavingTransaction.objects.create(
                goal=goal,
                automatic_saving=automatic_saving,
                amount=saving_amount,
                transaction_type=(
                    GoalSavingTransaction.TransactionType.DEPOSIT
                ),
                source=GoalSavingTransaction.Source.AUTOMATIC,
            )

            goal.current_amount += saving_amount

            if goal.current_amount >= goal.target_amount:
                goal.current_amount = goal.target_amount
                goal.status = FinancialGoal.Status.COMPLETED
                automatic_saving.is_active = False

            goal.save(
                update_fields=[
                    "current_amount",
                    "status",
                    "updated_at",
                ],
            )

            automatic_saving.last_run_at = now

            if automatic_saving.is_active:
                automatic_saving.next_run_at = calculate_next_run_at(
                    now,
                    automatic_saving.frequency,
                    automatic_saving.interval,
                )

            automatic_saving.save(
                update_fields=[
                    "last_run_at",
                    "next_run_at",
                    "is_active",
                    "updated_at",
                ],
            )

            processed += 1

    return {"processed": processed}
