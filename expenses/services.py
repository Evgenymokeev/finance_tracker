from decimal import Decimal

from .models import Expense


def create_expense(
    *,
    user,
    title,
    amount,
    category,
    date,
    description="",
):
    return Expense.objects.create(
        user=user,
        title=title,
        amount=Decimal(str(amount)),
        category=category,
        date=date,
        description=description or "",
    )