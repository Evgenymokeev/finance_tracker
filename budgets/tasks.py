from celery import shared_task

from notifications.models import Notification

from .models import Budget
from .services import calculate_budget_spending


@shared_task
def check_budget_exceeded(budget_id):
    """
    Проверяет превышение месячного бюджета.

    Сумма расходов рассчитывается сервисом с учётом валюты
    бюджета и конвертации расходов по историческим курсам.
    """

    try:
        budget = Budget.objects.select_related(
            "user",
            "category",
        ).get(
            id=budget_id,
        )
    except Budget.DoesNotExist:
        return f"Budget {budget_id} not found"

    # Рассчитываем расходы в валюте бюджета.
    spent_amount = calculate_budget_spending(budget)

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