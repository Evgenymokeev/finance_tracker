from datetime import date
from decimal import Decimal
from unittest.mock import Mock
from urllib.request import Request

from django.test import SimpleTestCase

from currency.providers.ecb_http import fetch_ecb_rates


class FetchECBRatesTests(SimpleTestCase):
    """Проверяет HTTP-загрузчик курсов ECB без реальных запросов."""

    def setUp(self):
        """Подготавливает фиктивный CSV-ответ ECB."""
        self.rate_date = date(2026, 10, 14)

        self.csv_content = (
            "KEY,FREQ,CURRENCY,TIME_PERIOD,OBS_VALUE\n"
            "EXR.D.CZK.EUR.SP00.A,D,CZK,2026-10-14,24.500\n"
            "EXR.D.USD.EUR.SP00.A,D,USD,2026-10-14,1.1600\n"
        ).encode("utf-8")

        self.response = Mock()
        self.response.read.return_value = self.csv_content
        self.response.__enter__ = Mock(
            return_value=self.response,
        )
        self.response.__exit__ = Mock(return_value=False)

        self.opener = Mock(return_value=self.response)

    def test_fetches_rates_for_requested_date(self):
        """
        Проверяет получение курсов за заданную дату
        и преобразование значений в Decimal.
        """
        rates = fetch_ecb_rates(
            self.rate_date,
            opener=self.opener,
        )

        self.assertEqual(
            rates,
            {
                "CZK": Decimal("24.500"),
                "USD": Decimal("1.1600"),
            },
        )

    def test_request_contains_requested_date(self):
        """Проверяет, что HTTP-запрос ограничен нужной датой."""
        fetch_ecb_rates(
            self.rate_date,
            opener=self.opener,
        )

        request = self.opener.call_args.args[0]

        self.assertIsInstance(request, Request)
        self.assertIn(
            "startPeriod=2026-10-14",
            request.full_url,
        )
        self.assertIn(
            "endPeriod=2026-10-14",
            request.full_url,
        )

    def test_empty_response_returns_empty_dictionary(self):
        """Проверяет обработку ответа без опубликованных курсов."""
        self.response.read.return_value = (
            "KEY,FREQ,CURRENCY,TIME_PERIOD,OBS_VALUE\n"
        ).encode("utf-8")

        rates = fetch_ecb_rates(
            self.rate_date,
            opener=self.opener,
        )

        self.assertEqual(rates, {})

    def test_rates_from_another_date_are_ignored(self):
        """Не допускает сохранения курса с другой датой."""
        self.response.read.return_value = (
            "KEY,FREQ,CURRENCY,TIME_PERIOD,OBS_VALUE\n"
            "EXR.D.CZK.EUR.SP00.A,D,CZK,2026-10-13,24.400\n"
        ).encode("utf-8")

        rates = fetch_ecb_rates(
            self.rate_date,
            opener=self.opener,
        )

        self.assertEqual(rates, {})

    def test_http_error_is_propagated(self):
        """Проверяет, что ошибка HTTP не маскируется."""
        self.opener.side_effect = TimeoutError(
            "ECB request timed out",
        )

        with self.assertRaises(TimeoutError):
            fetch_ecb_rates(
                self.rate_date,
                opener=self.opener,
            )