from datetime import date
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from currency.tasks import update_exchange_rates


class UpdateExchangeRatesTaskTests(SimpleTestCase):
    """Проверяет Celery-задачу обновления курсов валют."""

    @patch("currency.tasks.RateService")
    @patch("currency.tasks.get_exchange_rate_provider")
    def test_updates_rates_for_requested_date(
        self,
        provider_factory,
        service_class,
    ):
        """
        Проверяет передачу выбранного источника
        и даты в сервис обновления курсов.
        """

        provider = Mock()
        provider_factory.return_value = provider

        service = service_class.return_value
        service.update_rates.return_value = 12

        result = update_exchange_rates(
            source="ecb",
            rate_date="2026-10-14",
        )

        provider_factory.assert_called_once_with("ecb")
        service_class.assert_called_once_with(
            provider=provider,
        )
        service.update_rates.assert_called_once_with(
            date(2026, 10, 14),
        )

        self.assertEqual(
            result,
            {
                "source": "ecb",
                "date": "2026-10-14",
                "processed": 12,
            },
        )

    @patch("currency.tasks.RateService")
    @patch("currency.tasks.get_exchange_rate_provider")
    def test_empty_result_is_reported(
        self,
        provider_factory,
        service_class,
    ):
        """Проверяет корректную обработку отсутствующих курсов."""

        provider_factory.return_value = Mock()
        service_class.return_value.update_rates.return_value = 0

        result = update_exchange_rates(
            source="cbr",
            rate_date="2026-10-11",
        )

        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["source"], "cbr")

    def test_invalid_date_raises_value_error(self):
        """Проверяет отказ от некорректной даты."""

        with self.assertRaisesMessage(
            ValueError,
            "rate_date must be in YYYY-MM-DD format",
        ):
            update_exchange_rates(
                source="ecb",
                rate_date="14-10-2026",
            )

    def test_impossible_date_raises_value_error(self):
        """Проверяет отказ от несуществующей календарной даты."""

        with self.assertRaises(ValueError):
            update_exchange_rates(
                source="ecb",
                rate_date="2026-02-30",
            )

    @patch("currency.tasks.get_exchange_rate_provider")
    def test_unknown_source_error_is_propagated(
        self,
        provider_factory,
    ):
        """Проверяет передачу ошибки неизвестного источника."""

        provider_factory.side_effect = ValueError(
            "Unsupported exchange rate source: unknown"
        )

        with self.assertRaisesMessage(
            ValueError,
            "Unsupported exchange rate source: unknown",
        ):
            update_exchange_rates(
                source="unknown",
                rate_date="2026-10-14",
            )

    @patch("currency.tasks.RateService")
    @patch("currency.tasks.get_exchange_rate_provider")
    def test_service_error_is_propagated(
        self,
        provider_factory,
        service_class,
    ):
        """Проверяет, что ошибка обновления не скрывается."""

        provider_factory.return_value = Mock()
        service_class.return_value.update_rates.side_effect = (
            RuntimeError("Database unavailable")
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "Database unavailable",
        ):
            update_exchange_rates(
                source="ecb",
                rate_date="2026-10-14",
            )