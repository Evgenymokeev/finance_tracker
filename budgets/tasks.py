from decimal import Decimal

from celery import shared_task
from django.db.models import Sum

from expenses.models import Expense
from notifications.models import Notification

from .models import Budget


@shared_task
def check_budget_exceeded(budget_id):
    try:
        budget = Budget.objects.select_related(
            "user",
            "category",
        ).get(
            id=budget_id,
        )
    except Budget.DoesNotExist:
        return f"Budget {budget_id} not found"

    spent_amount = (
        Expense.objects
        .filter(
            user=budget.user,
            category=budget.category,
            date__year=budget.month.year,
            date__month=budget.month.month,
        )
        .aggregate(
            total=Sum("amount"),
        )
        .get("total")
        or Decimal("0.00")
    )

    if spent_amount <= budget.amount:
        return {
            "budget_id": budget.id,
            "status": "within_limit",
            "budget_amount": str(budget.amount),
            "spent_amount": str(spent_amount),
        }

    notification, created = Notification.objects.get_or_create(
        user=budget.user,
        budget=budget,
        notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
        defaults={
            "title": "Budget exceeded",
            "message": (
                f"Your budget for "
                f"{budget.category.name} "
                f"for {budget.month:%Y-%m} "
                f"has been exceeded."
            ),
        },
    )

    return {
        "budget_id": budget.id,
        "status": "exceeded",
        "budget_amount": str(budget.amount),
        "spent_amount": str(spent_amount),
        "notification_created": created,
        "notification_id": notification.id,
    }