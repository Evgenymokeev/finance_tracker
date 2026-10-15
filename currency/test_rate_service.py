from datetime import date
from decimal import Decimal
from unittest.mock import Mock

from django.test import SimpleTestCase

from currency.providers.base import (
    ExchangeRateData,
    ExchangeRateProvider,
)
from currency.rate_service import RateService
from currency.rate_updater import RateUpdater


class RateServiceTests(SimpleTestCase):
    """
    Проверяет взаимодействие RateService с Provider и RateUpdater.

    Тесты не обращаются к внешним API и базе данных.
    Зависимости заменяются mock-объектами.
    """

    def setUp(self):
        """
        Подготавливает общие тестовые данные и зависимости.

        Создаёт дату обновления, два нормализованных курса,
        имитацию Provider и имитацию RateUpdater.
        """

        self.rate_date = date(2026, 10, 15)

        self.rates = [
            ExchangeRateData(
                base_currency="EUR",
                target_currency="CZK",
                rate=Decimal("24.5000000000"),
                date=self.rate_date,
            ),
            ExchangeRateData(
                base_currency="EUR",
                target_currency="USD",
                rate=Decimal("1.1600000000"),
                date=self.rate_date,
            ),
        ]

        self.provider = Mock(spec=ExchangeRateProvider)
        self.updater = Mock(spec=RateUpdater)

        self.provider.get_rates.return_value = self.rates
        self.updater.update.return_value = 2

        self.service = RateService(
            provider=self.provider,
            updater=self.updater,
        )

    def test_passes_date_to_provider(self):
        """
        Проверяет, что сервис передаёт Provider запрошенную дату.

        Provider должен получить именно ту дату, которую
        передали в RateService.update_rates().
        """

        self.service.update_rates(self.rate_date)

        self.provider.get_rates.assert_called_once_with(
            self.rate_date
        )

    def test_passes_provider_rates_to_updater(self):
        """
        Проверяет передачу полученных курсов в RateUpdater.

        Сервис должен передать результат Provider без изменения
        и не должен самостоятельно преобразовывать курсы.
        """

        self.service.update_rates(self.rate_date)

        self.updater.update.assert_called_once_with(
            self.rates
        )

    def test_returns_number_of_processed_rates(self):
        """
        Проверяет возврат количества обработанных курсов.

        Сервис должен вернуть результат RateUpdater,
        а не самостоятельно подсчитывать количество записей.
        """

        result = self.service.update_rates(self.rate_date)

        self.assertEqual(result, 2)

    def test_empty_source_returns_zero(self):
        """
        Проверяет обработку ситуации, когда Provider
        не вернул ни одного курса.

        Пустой список передаётся RateUpdater.
        Сервис возвращает полученный от него результат — ноль.
        """

        self.provider.get_rates.return_value = []
        self.updater.update.return_value = 0

        result = self.service.update_rates(self.rate_date)

        self.assertEqual(result, 0)
        self.provider.get_rates.assert_called_once_with(
            self.rate_date
        )
        self.updater.update.assert_called_once_with([])

    def test_provider_error_does_not_call_updater(self):
        """
        Проверяет, что ошибка Provider останавливает обновление.

        Если получение курсов завершилось ошибкой, RateUpdater
        не должен вызываться, а исключение должно передаваться
        вызывающему коду.
        """

        self.provider.get_rates.side_effect = RuntimeError(
            "Provider unavailable"
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Provider unavailable",
        ):
            self.service.update_rates(self.rate_date)

        self.updater.update.assert_not_called()

    def test_propagates_updater_error(self):
        """
        Проверяет передачу исключения от RateUpdater.

        Сервис не должен скрывать ошибку валидации или сохранения
        курсов и подменять её другим результатом.
        """

        self.updater.update.side_effect = RuntimeError(
            "Database error"
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Database error",
        ):
            self.service.update_rates(self.rate_date)

        self.provider.get_rates.assert_called_once_with(
            self.rate_date
        )
        self.updater.update.assert_called_once_with(
            self.rates
        )

    def test_creates_default_updater_when_not_provided(self):
        """
        Проверяет создание стандартного RateUpdater,
        если он не передан при инициализации сервиса.

        При этом переданный Provider должен сохраняться
        в качестве источника курсов.
        """

        service = RateService(provider=self.provider)

        self.assertIs(service.provider, self.provider)
        self.assertIsInstance(service.updater, RateUpdater)
