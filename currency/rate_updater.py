from collections.abc import Iterable

from django.db import transaction

from users.models import UserSettings

from .models import ExchangeRate
from .providers.base import ExchangeRateData


class RateUpdater:
    """
    Сохраняет нормализованные курсы валют
    в базе данных.

    Provider отвечает за получение и нормализацию
    данных.

    RateUpdater отвечает за validation
    и persistence.
    """

    @transaction.atomic
    def update(
        self,
        rates: Iterable[ExchangeRateData],
    ) -> int:
        """
        Сохраняет переданные курсы валют.

        Если курс для пары валют и даты уже существует,
        его значение обновляется.

        Возвращает количество обработанных курсов.

        Все изменения выполняются в рамках одной транзакции.
        При ошибке изменения откатываются.
        """

        count = 0

        for rate_data in rates:
            self._validate(rate_data)

            ExchangeRate.objects.update_or_create(
                base_currency=rate_data.base_currency,
                target_currency=rate_data.target_currency,
                date=rate_data.date,
                defaults={
                    "rate": rate_data.rate,
                },
            )

            count += 1

        return count

    @staticmethod
    def _validate(
        rate_data: ExchangeRateData,
    ) -> None:
        """
        Проверяет нормализованные данные курса
        перед сохранением.
        """

        valid_currencies = {
            currency
            for currency, _ in UserSettings.Currency.choices
        }

        if rate_data.base_currency not in valid_currencies:
            raise ValueError(
                f"Unsupported base currency: "
                f"{rate_data.base_currency}"
            )

        if rate_data.target_currency not in valid_currencies:
            raise ValueError(
                f"Unsupported target currency: "
                f"{rate_data.target_currency}"
            )

        if rate_data.base_currency == rate_data.target_currency:
            raise ValueError(
                "Base and target currencies must be different."
            )

        if rate_data.rate <= 0:
            raise ValueError(
                "Exchange rate must be positive."
            )