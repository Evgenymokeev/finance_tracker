from datetime import date
from decimal import Decimal
from unittest.mock import Mock

from django.test import SimpleTestCase

from currency.providers.base import ExchangeRateData
from currency.providers.cbr import CBRExchangeRateProvider
from currency.providers.ecb import ECBExchangeRateProvider


class ECBExchangeRateProviderTests(SimpleTestCase):
    def setUp(self):
        self.rate_date = date(2026, 10, 14)
        self.fetch_rates = Mock(
            return_value={
                "CZK": Decimal("24.357"),
                "USD": Decimal("1.160"),
                "JPY": Decimal("175.0"),
                "EUR": Decimal("1.0"),
            }
        )
        self.provider = ECBExchangeRateProvider(
            fetch_rates=self.fetch_rates,
        )

    def test_preserves_all_source_currencies(self):
        rates = self.provider.get_rates(self.rate_date)

        self.assertEqual(
            [
                (rate.base_currency, rate.target_currency)
                for rate in rates
            ],
            [
                ("EUR", "CZK"),
                ("EUR", "USD"),
                ("EUR", "JPY"),
                ("EUR", "EUR"),
            ],
        )

    def test_preserves_decimal_rates(self):
        rates = self.provider.get_rates(self.rate_date)

        self.assertEqual(
            [rate.rate for rate in rates],
            [
                Decimal("24.357"),
                Decimal("1.160"),
                Decimal("175.0"),
                Decimal("1.0"),
            ],
        )

    def test_passes_requested_date_to_fetcher(self):
        self.provider.get_rates(self.rate_date)

        self.fetch_rates.assert_called_once_with(self.rate_date)


class CBRExchangeRateProviderTests(SimpleTestCase):
    def setUp(self):
        self.rate_date = date(2026, 10, 14)
        self.fetch_rates = Mock(
            return_value={
                "CZK": Decimal("3.30"),
                "EUR": Decimal("90.0"),
                "USD": Decimal("80.0"),
                "JPY": Decimal("0.50"),
                "RUB": Decimal("1.0"),
            }
        )
        self.provider = CBRExchangeRateProvider(
            fetch_rates=self.fetch_rates,
        )

    def test_preserves_all_source_currencies(self):
        rates = self.provider.get_rates(self.rate_date)

        self.assertEqual(
            [
                (rate.base_currency, rate.target_currency)
                for rate in rates
            ],
            [
                ("CZK", "RUB"),
                ("EUR", "RUB"),
                ("USD", "RUB"),
                ("JPY", "RUB"),
                ("RUB", "RUB"),
            ],
        )

    def test_preserves_decimal_rates(self):
        rates = self.provider.get_rates(self.rate_date)

        self.assertEqual(
            [rate.rate for rate in rates],
            [
                Decimal("3.30"),
                Decimal("90.0"),
                Decimal("80.0"),
                Decimal("0.50"),
                Decimal("1.0"),
            ],
        )

    def test_passes_requested_date_to_fetcher(self):
        self.provider.get_rates(self.rate_date)

        self.fetch_rates.assert_called_once_with(self.rate_date)
