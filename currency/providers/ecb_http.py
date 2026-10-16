import csv
from datetime import date
from decimal import Decimal
from io import StringIO
from typing import Callable
from urllib.request import Request, urlopen


ECB_DAILY_RATES_URL = (
    "https://data-api.ecb.europa.eu/service/data/EXR/"
    "D..EUR.SP00.A"
)


def fetch_ecb_rates(
    rate_date: date,
    opener: Callable = urlopen,
) -> dict[str, Decimal]:
    """
    Получает справочные курсы ECB за конкретную дату.

    Используется официальный API ECB с CSV-ответом.
    Запрос ограничен одной датой, поэтому курсы
    не смешиваются с данными за другие дни.

    Если на указанную дату курсы не опубликованы,
    возвращается пустой словарь.

    opener передаётся через dependency injection,
    чтобы тестировать загрузчик без реальных HTTP-запросов.
    """

    date_parameter = rate_date.isoformat()

    url = (
        f"{ECB_DAILY_RATES_URL}"
        f"?startPeriod={date_parameter}"
        f"&endPeriod={date_parameter}"
        "&format=csvdata"
    )

    request = Request(
        url,
        headers={
            "User-Agent": "finance-tracker/1.0",
            "Accept": "text/csv",
        },
    )

    with opener(request, timeout=10) as response:
        csv_content = response.read().decode("utf-8-sig")

    reader = csv.DictReader(StringIO(csv_content))
    rates = {}

    for row in reader:
        if row.get("TIME_PERIOD") != date_parameter:
            continue

        currency = row.get("CURRENCY")
        value = row.get("OBS_VALUE")

        if not currency or not value:
            continue

        rates[currency] = Decimal(value)

    return rates