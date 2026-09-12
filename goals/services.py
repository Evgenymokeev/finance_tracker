import calendar

from datetime import datetime

from dateutil.relativedelta import relativedelta

from .models import GoalAutomaticSaving


def calculate_next_run_at(
    current_run_at: datetime,
    frequency: str,
    interval: int | None = None,
) -> datetime:
    """
    Рассчитывает дату следующего автоматического накопления.

    Правила:
    - daily   -> +1 день
    - weekly  -> +7 дней
    - monthly -> следующий месяц
    - yearly  -> следующий год
    - custom  -> +interval дней
    """

    if frequency == GoalAutomaticSaving.Frequency.DAILY:
        return current_run_at + relativedelta(days=1)

    if frequency == GoalAutomaticSaving.Frequency.WEEKLY:
        return current_run_at + relativedelta(days=7)

    if frequency == GoalAutomaticSaving.Frequency.MONTHLY:
        return current_run_at + relativedelta(months=1)

    if frequency == GoalAutomaticSaving.Frequency.YEARLY:
        return current_run_at + relativedelta(years=1)

    if frequency == GoalAutomaticSaving.Frequency.CUSTOM:
        if interval is None or interval <= 0:
            raise ValueError(
                "Interval must be greater than zero "
                "for custom frequency."
            )

        return current_run_at + relativedelta(
            days=interval
        )

    raise ValueError(
        f"Unsupported frequency: {frequency}"
    )