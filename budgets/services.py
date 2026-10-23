"""
Сервисы расчёта расходов и прогресса бюджета.
"""

from datetime import date
from decimal import Decimal

from currency.services import convert_expense_amount
from expenses.models import Expense

from .models import Budget


def calculate_budget_spending(budget: Budget) -> Decimal:
    """
    Рассчитывает сумму расходов за месяц в валюте бюджета.

    Каждый расход конвертируется отдельно по историческому
    курсу, актуальному на дату самого расхода.

    Если расход уже выражен в валюте бюджета, конвертация
    не требует наличия курса.

    Если для конвертации хотя бы одного расхода не хватает
    курса, ExchangeRate.DoesNotExist передаётся вызывающему
    коду. Частичная сумма в таком случае не возвращается.

    Исходные записи Expense не изменяются.
    """

    # Определяем границы месяца: начало текущего и начало
    # следующего месяца. Это также корректно работает в декабре.
    start_date = date(
        budget.month.year,
        budget.month.month,
        1,
    )

    if start_date.month == 12:
        next_month = date(
            start_date.year + 1,
            1,
            1,
        )
    else:
        next_month = date(
            start_date.year,
            start_date.month + 1,
            1,
        )

    expenses = Expense.objects.filter(
        user=budget.user,
        category=budget.category,
        date__gte=start_date,
        date__lt=next_month,
    ).order_by("date", "id")

    spent_amount = Decimal("0.00")

    for expense in expenses:
        # Конвертируем каждый расход в валюту бюджета.
        # Ошибку отсутствующего курса намеренно не подавляем.
        converted_amount = convert_expense_amount(
            expense=expense,
            target_currency=budget.currency,
        )

        spent_amount += converted_amount

    return spent_amount