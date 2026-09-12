from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import FinancialGoal, GoalAutomaticSaving
from .services import calculate_next_run_at


@shared_task
def process_automatic_savings():
    now = timezone.now()

    automatic_savings = (
        GoalAutomaticSaving.objects
        .select_related("goal")
        .filter(
            is_active=True,
            next_run_at__lte=now,
            goal__status=FinancialGoal.Status.ACTIVE,
        )
    )

    processed = 0

    for automatic_saving in automatic_savings:
        with transaction.atomic():
            automatic_saving = (
                GoalAutomaticSaving.objects
                .select_for_update()
                .select_related("goal")
                .get(id=automatic_saving.id)
            )

            if (
                not automatic_saving.is_active
                or automatic_saving.next_run_at > now
                or automatic_saving.goal.status
                != FinancialGoal.Status.ACTIVE
            ):
                continue

            goal = automatic_saving.goal

            goal.current_amount += automatic_saving.amount

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

    return {
        "processed": processed,
    }