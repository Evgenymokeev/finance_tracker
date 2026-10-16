from django.test import SimpleTestCase

from currency.providers.base import ExchangeRateProvider
from currency.providers.cbr import CBRExchangeRateProvider
from currency.providers.ecb import ECBExchangeRateProvider
from currency.providers.factory import get_exchange_rate_provider


class ExchangeRateProviderFactoryTests(SimpleTestCase):
    """Проверяет создание Provider для разных источников."""

    def test_creates_ecb_provider(self):
        """Проверяет создание Provider Европейского центрального банка."""
        provider = get_exchange_rate_provider("ecb")

        self.assertIsInstance(
            provider,
            ECBExchangeRateProvider,
        )
        self.assertIsInstance(
            provider,
            ExchangeRateProvider,
        )

    def test_creates_cbr_provider(self):
        """Проверяет создание Provider Центрального банка России."""
        provider = get_exchange_rate_provider("cbr")

        self.assertIsInstance(
            provider,
            CBRExchangeRateProvider,
        )
        self.assertIsInstance(
            provider,
            ExchangeRateProvider,
        )

    def test_source_is_case_insensitive(self):
        """Проверяет поддержку идентификатора источника в верхнем регистре."""
        provider = get_exchange_rate_provider("ECB")

        self.assertIsInstance(
            provider,
            ECBExchangeRateProvider,
        )

    def test_unknown_source_raises_value_error(self):
        """Проверяет отказ от неизвестного источника курсов."""
        with self.assertRaisesMessage(
            ValueError,
            "Unsupported exchange rate source: unknown",
        ):
            get_exchange_rate_provider("unknown")