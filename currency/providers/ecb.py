from datetime import date
from decimal import Decimal
from typing import Callable

from .base import ExchangeRateData, ExchangeRateProvider


class ECBExchangeRateProvider(ExchangeRateProvider):
    """
    Provider курсов валют Европейского центрального банка.

    Provider получает и нормализует данные ECB.
    Сохранение выполняется отдельным application/service слоем.
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
                base_currency="EUR",
                target_currency=currency,
                rate=rate,
                date=rate_date,
            )
            for currency, rate in rates.items()
        ]
