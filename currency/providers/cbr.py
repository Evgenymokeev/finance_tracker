from datetime import date
from decimal import Decimal
from typing import Callable

from .base import ExchangeRateData, ExchangeRateProvider


class CBRExchangeRateProvider(ExchangeRateProvider):
    """
    Provider курсов валют Центрального банка России.

    CBR публикует курсы иностранных валют
    относительно российского рубля.

    Например:

        USD = 80.50 RUB

    означает:

        1 USD = 80.50 RUB

    Provider преобразует эти данные
    в нормализованный формат ExchangeRateData.

    Сохранение курсов в базу данных выполняется
    отдельным application/service слоем.
    """

    def __init__(
        self,
        fetch_rates: Callable[[date], dict[str, Decimal]],
    ):
        """
        Принимает функцию получения курсов CBR.

        Dependency injection позволяет тестировать provider
        без реальных HTTP-запросов.
        """

        self.fetch_rates = fetch_rates

    def get_rates(
        self,
        rate_date: date,
    ) -> list[ExchangeRateData]:
        """
        Получает курсы CBR и преобразует их
        в нормализованный формат ExchangeRateData.

        CBR предоставляет курсы относительно RUB,
        поэтому базовой валютой результата является RUB
        только для обратного направления? Нет:

        исходный CBR курс:

            USD → RUB

        поэтому provider сохраняет:

            base_currency = USD
            target_currency = RUB
        """

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