from datetime import date as date_type
from decimal import Decimal

from django.conf import settings

from budgets.models import Budget
from budgets.tasks import check_budget_exceeded

from .models import Expense
from .tasks import send_expense_notification


def create_expense(
    *,
    user,
    title,
    amount,
    category,
    date,
    description="",
):
    if isinstance(date, str):
        date = date_type.fromisoformat(date)

    expense = Expense.objects.create(
        user=user,
        title=title,
        amount=Decimal(str(amount)),
        category=category,
        date=date,
        description=description or "",
    )

    if not settings.TESTING:
        send_expense_notification.delay(expense.id)

        budget = Budget.objects.filter(
            user=user,
            category=category,
            month__year=expense.date.year,
            month__month=expense.date.month,
        ).first()

        if budget:
            check_budget_exceeded.delay(budget.id)

    return expense