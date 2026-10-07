from datetime import date
from decimal import Decimal
from typing import Callable
from urllib.request import Request, urlopen

from .cbr_fetcher import parse_cbr_rates


CBR_DAILY_RATES_URL = (
    "https://www.cbr.ru/scripts/XML_daily.asp"
)


def fetch_cbr_rates(
    rate_date: date,
    opener: Callable = urlopen,
) -> dict[str, Decimal]:
    """
    Получает курсы валют Банка России
    на указанную дату.

    Используется официальный XML endpoint CBR:

        XML_daily.asp?date_req=DD/MM/YYYY

    HTTP-запрос выполняется здесь,
    а разбор XML делегируется функции
    parse_cbr_rates().

    opener передаётся через dependency injection,
    чтобы HTTP-запрос можно было тестировать
    без реального обращения к Банку России.
    """

    date_parameter = rate_date.strftime("%d/%m/%Y")

    url = (
        f"{CBR_DAILY_RATES_URL}"
        f"?date_req={date_parameter}"
    )

    request = Request(
        url,
        headers={
            "User-Agent": "finance-tracker/1.0",
        },
    )

    with opener(
        request,
        timeout=10,
    ) as response:
        xml_content = response.read()

    return parse_cbr_rates(xml_content)
