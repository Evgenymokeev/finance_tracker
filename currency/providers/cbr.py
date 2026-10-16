from datetime import date
from decimal import Decimal
from typing import Callable

from .base import ExchangeRateData, ExchangeRateProvider


class CBRExchangeRateProvider(ExchangeRateProvider):
    """
    Provider курсов валют Центрального банка России.

    CBR публикует курсы иностранных валют относительно RUB.
    Provider нормализует данные, не фильтруя исходные валюты.
    """

    def __init__(
        self,
        fetch_rates: Callable[[date], dict[str, Decimal]],
    ):
        self.fetch_rates = fetch_rates

    def get_rates(
        self,
        rate_date: date,
    ) -> list[ExchangeRateData]:
        rates = self.fetch_rates(rate_date)

        return [
            ExchangeRateData(
                base_currency=currency,
                target_currency="RUB",
                rate=rate,
                date=rate_date,
            )
            for currency, rate in rates.items()
        ]
