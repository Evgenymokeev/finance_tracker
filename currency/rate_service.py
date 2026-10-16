from datetime import date

from users.models import UserSettings

from .providers.base import ExchangeRateProvider
from .rate_updater import RateUpdater


class RateService:
    def __init__(
        self,
        provider: ExchangeRateProvider,
        updater: RateUpdater | None = None,
    ) -> None:
        self.provider = provider
        self.updater = updater if updater is not None else RateUpdater()

    def update_rates(self, rate_date: date) -> int:
        rates = self.provider.get_rates(rate_date)

        supported_currencies = {
            currency
            for currency, _ in UserSettings.Currency.choices
        }

        supported_rates = [
            rate
            for rate in rates
            if rate.base_currency in supported_currencies
            and rate.target_currency in supported_currencies
            and rate.base_currency != rate.target_currency
        ]

        return self.updater.update(supported_rates)
