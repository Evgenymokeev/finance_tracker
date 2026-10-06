from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .models import ExchangeRate


def get_exchange_rate(
    base_currency: str,
    target_currency: str,
    rate_date: date,
) -> Decimal:
    """
    Возвращает последний доступный курс валют
    на указанную дату или ранее.

    Например:

        EUR → CZK
        дата операции: 2026-10-06

    Если курс существует именно на эту дату,
    возвращается он.

    Если курса на эту дату нет, но есть курс
    на более раннюю дату, возвращается последний
    доступный курс.

    Если подходящего курса нет вообще,
    вызывается ExchangeRate.DoesNotExist.
    """

    exchange_rate = (
        ExchangeRate.objects
        .filter(
            base_currency=base_currency,
            target_currency=target_currency,
            date__lte=rate_date,
        )
        .order_by("-date")
        .first()
    )

    if exchange_rate is None:
        raise ExchangeRate.DoesNotExist(
            f"Exchange rate not found: "
            f"{base_currency} → {target_currency} "
            f"for {rate_date}"
        )

    return exchange_rate.rate

def convert_currency(
    amount: Decimal,
    base_currency: str,
    target_currency: str,
    rate_date: date,
    decimal_places: int = 2,
) -> Decimal:
    """
    Конвертирует денежную сумму из одной валюты
    в другую по историческому курсу.

    Например:

        100 EUR
        EUR → CZK
        дата: 2026-10-06

    Сначала сервис получает исторический курс
    через get_exchange_rate(), затем умножает
    сумму на курс.

    Результат округляется до указанного количества
    знаков после запятой.

    По умолчанию используется 2 знака после запятой,
    что подходит для отображения денежных сумм.
    """

    if amount < 0:
        raise ValueError(
            "Amount cannot be negative."
        )

    if decimal_places < 0:
        raise ValueError(
            "Decimal places cannot be negative."
        )

    if base_currency == target_currency:
        return amount.quantize(
            Decimal("1").scaleb(-decimal_places),
            rounding=ROUND_HALF_UP,
        )

    rate = get_exchange_rate(
        base_currency=base_currency,
        target_currency=target_currency,
        rate_date=rate_date,
    )

    converted_amount = amount * rate

    quantizer = Decimal("1").scaleb(-decimal_places)

    return converted_amount.quantize(
        quantizer,
        rounding=ROUND_HALF_UP,
    )

def convert_expense_amount(
    expense,
    target_currency: str,
    decimal_places: int = 2,
) -> Decimal:
    """
    Конвертирует сумму расхода в указанную валюту.

    Использует данные самого расхода:

        expense.amount
        expense.currency
        expense.date

    Исторический курс определяется автоматически
    по дате расхода.

    Например:

        Expense:
            amount = 100.00
            currency = EUR
            date = 2026-10-06

        target_currency = CZK

    Результат:

        2531.65
    """

    return convert_currency(
        amount=expense.amount,
        base_currency=expense.currency,
        target_currency=target_currency,
        rate_date=expense.date,
        decimal_places=decimal_places,
    )