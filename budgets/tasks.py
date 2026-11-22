from celery import shared_task
from notifications.models import Notification
from notifications.orchestrators import NotificationOrchestrator

from .models import Budget
from .services import calculate_budget_spending


@shared_task
def check_budget_exceeded(budget_id):
    """
    Проверяет превышение месячного бюджета.

    Сумма расходов рассчитывается сервисом с учётом валюты
    бюджета и конвертации расходов по историческим курсам.

    При превышении создаётся уведомление через
    NotificationOrchestrator, который обеспечивает
    идемпотентность и подготовку разрешённых каналов доставки.
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
    # Если исторического курса нет, исключение передаётся выше:
    # уведомление в таком случае создавать нельзя.
    spent_amount = calculate_budget_spending(budget)

    if spent_amount <= budget.amount:
        return {
            "budget_id": budget.id,
            "status": "within_limit",
            "budget_amount": str(budget.amount),
            "spent_amount": str(spent_amount),
        }

    # Сохраняем контекст события на момент превышения.
    # Строки используются для точного представления Decimal
    # и совместимости с JSONField.
    notification_data = {
        "budget_id": budget.id,
        "category_id": budget.category_id,
        "category_name": budget.category.name,
        "budget_amount": str(budget.amount),
        "spent_amount": str(spent_amount),
        "currency": budget.currency,
        "month": budget.month.strftime("%Y-%m"),
    }

    # Оркестратор атомарно создаёт уведомление и разрешённые
    # записи доставки, если такое событие ещё не обрабатывалось.
    notification, created = NotificationOrchestrator.create(
        user=budget.user,
        notification_type=Notification.NotificationType.BUDGET_EXCEEDED,
        event_key=f"budget:{budget.id}:budget_exceeded",
        title="Budget exceeded",
        message=(
            f"Your budget for "
            f"{budget.category.name} "
            f"for {budget.month:%Y-%m} "
            f"has been exceeded."
        ),
        data=notification_data,
        budget=budget,
    )

    return {
        "budget_id": budget.id,
        "status": "exceeded",
        "budget_amount": str(budget.amount),
        "spent_amount": str(spent_amount),
        "notification_created": created,
        "notification_id": notification.id,
    }
