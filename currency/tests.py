from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from categories.models import Category
from expenses.models import Expense
from .rate_updater import RateUpdater
from .models import ExchangeRate
from .providers.base import (
    ExchangeRateData,
    ExchangeRateProvider,
)
from .providers.ecb import ECBExchangeRateProvider
from .providers.cbr import CBRExchangeRateProvider
from .providers.ecb_fetcher import parse_ecb_rates
from .providers.cbr_fetcher import parse_cbr_rates
from .providers.cbr_http import fetch_cbr_rates
from .services import (
    convert_currency,
    convert_expense_amount,
    get_exchange_rate,
)

class ExchangeRateModelTests(TestCase):
    """
    Тесты модели ExchangeRate.

    Проверяют создание валютного курса,
    валидацию полей и ограничения базы данных.
    """

    def setUp(self):
        """
        Создаёт базовый валютный курс
        для тестов ExchangeRate.
        """

        self.exchange_rate = ExchangeRate(
            base_currency="CZK",
            target_currency="EUR",
            rate=Decimal("0.0395000000"),
            date=date(2026, 10, 6),
        )

    def test_create_exchange_rate(self):
        """
        Проверяет корректное создание валютного курса.
        """

        self.exchange_rate.full_clean()
        self.exchange_rate.save()

        self.assertEqual(
            ExchangeRate.objects.count(),
            1,
        )

        self.assertEqual(
            self.exchange_rate.base_currency,
            "CZK",
        )

        self.assertEqual(
            self.exchange_rate.target_currency,
            "EUR",
        )

        self.assertEqual(
            self.exchange_rate.rate,
            Decimal("0.0395000000"),
        )

        self.assertEqual(
            self.exchange_rate.date,
            date(2026, 10, 6),
        )

    def test_rate_is_decimal(self):
        """
        Проверяет, что курс хранится как Decimal.
        """

        self.exchange_rate.full_clean()
        self.exchange_rate.save()

        self.assertIsInstance(
            self.exchange_rate.rate,
            Decimal,
        )

    def test_zero_rate_is_invalid(self):
        """
        Проверяет, что нулевой курс недопустим.
        """

        self.exchange_rate.rate = Decimal("0")

        with self.assertRaises(ValidationError):
            self.exchange_rate.full_clean()

    def test_negative_rate_is_invalid(self):
        """
        Проверяет, что отрицательный курс недопустим.
        """

        self.exchange_rate.rate = Decimal("-1.0000000000")

        with self.assertRaises(ValidationError):
            self.exchange_rate.full_clean()

    def test_same_currency_is_invalid(self):
        """
        Проверяет, что базовая и целевая валюты
        не могут быть одинаковыми.
        """

        self.exchange_rate.target_currency = "CZK"

        with self.assertRaises(ValidationError):
            self.exchange_rate.full_clean()

    def test_duplicate_rate_for_same_day_is_invalid(self):
        """
        Проверяет, что нельзя создать два курса
        одной и той же пары валют на одну дату.
        """

        self.exchange_rate.save()

        duplicate_rate = ExchangeRate(
            base_currency="CZK",
            target_currency="EUR",
            rate=Decimal("0.0400000000"),
            date=date(2026, 10, 6),
        )

        with self.assertRaises(IntegrityError):
            duplicate_rate.save()

    def test_same_pair_can_exist_on_different_dates(self):
        """
        Проверяет, что одна и та же пара валют
        может иметь разные курсы на разные даты.
        """

        self.exchange_rate.save()

        another_rate = ExchangeRate(
            base_currency="CZK",
            target_currency="EUR",
            rate=Decimal("0.0400000000"),
            date=date(2026, 10, 7),
        )

        another_rate.full_clean()
        another_rate.save()

        self.assertEqual(
            ExchangeRate.objects.count(),
            2,
        )

    def test_reverse_currency_pair_is_allowed(self):
        """
        Проверяет, что обратная валютная пара
        является отдельным допустимым курсом.

        Например:

            CZK → EUR
            EUR → CZK
        """

        self.exchange_rate.save()

        reverse_rate = ExchangeRate(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("25.3164556962"),
            date=date(2026, 10, 6),
        )

        reverse_rate.full_clean()
        reverse_rate.save()

        self.assertEqual(
            ExchangeRate.objects.count(),
            2,
        )

    def test_string_representation(self):
        """
        Проверяет строковое представление валютного курса.
        """

        self.assertEqual(
            str(self.exchange_rate),
            "CZK → EUR: 0.0395000000 (2026-10-06)",
        )

    def test_default_ordering(self):
        """
        Проверяет сортировку курсов по дате:
        сначала самые новые.
        """

        older_rate = ExchangeRate(
            base_currency="CZK",
            target_currency="EUR",
            rate=Decimal("0.0380000000"),
            date=date(2026, 10, 5),
        )

        newer_rate = ExchangeRate(
            base_currency="CZK",
            target_currency="EUR",
            rate=Decimal("0.0395000000"),
            date=date(2026, 10, 6),
        )

        older_rate.save()
        newer_rate.save()

        rates = list(
            ExchangeRate.objects.all()
        )

        self.assertEqual(
            rates[0].date,
            date(2026, 10, 6),
        )

        self.assertEqual(
            rates[1].date,
            date(2026, 10, 5),
        )

class ExchangeRateServiceTests(TestCase):
    """
    Тесты сервиса поиска исторического курса.
    """

    def setUp(self):
        """
        Создаёт несколько исторических курсов
        для тестов поиска.
        """

        ExchangeRate.objects.create(
            base_currency="CZK",
            target_currency="EUR",
            rate=Decimal("0.0380000000"),
            date=date(2026, 10, 1),
        )

        ExchangeRate.objects.create(
            base_currency="CZK",
            target_currency="EUR",
            rate=Decimal("0.0390000000"),
            date=date(2026, 10, 3),
        )

        ExchangeRate.objects.create(
            base_currency="CZK",
            target_currency="EUR",
            rate=Decimal("0.0395000000"),
            date=date(2026, 10, 6),
        )

    def test_get_rate_for_exact_date(self):
        """
        Проверяет получение курса,
        существующего точно на указанную дату.
        """

        rate = get_exchange_rate(
            base_currency="CZK",
            target_currency="EUR",
            rate_date=date(2026, 10, 3),
        )

        self.assertEqual(
            rate,
            Decimal("0.0390000000"),
        )

    def test_get_latest_rate_before_date(self):
        """
        Проверяет получение последнего доступного курса,
        если на указанную дату курса нет.
        """

        rate = get_exchange_rate(
            base_currency="CZK",
            target_currency="EUR",
            rate_date=date(2026, 10, 5),
        )

        self.assertEqual(
            rate,
            Decimal("0.0390000000"),
        )

    def test_get_latest_rate_on_or_before_date(self):
        """
        Проверяет, что сервис никогда не использует
        курс из будущего.

        Для даты 2026-10-04 должен использоваться
        курс от 2026-10-03, а не от 2026-10-06.
        """

        rate = get_exchange_rate(
            base_currency="CZK",
            target_currency="EUR",
            rate_date=date(2026, 10, 4),
        )

        self.assertEqual(
            rate,
            Decimal("0.0390000000"),
        )

    def test_get_rate_returns_newest_available_rate(self):
        """
        Проверяет, что при наличии нескольких
        подходящих курсов выбирается самый новый.
        """

        rate = get_exchange_rate(
            base_currency="CZK",
            target_currency="EUR",
            rate_date=date(2026, 10, 10),
        )

        self.assertEqual(
            rate,
            Decimal("0.0395000000"),
        )

    def test_missing_rate_raises_error(self):
        """
        Проверяет ошибку, если подходящего курса нет.
        """

        with self.assertRaises(ExchangeRate.DoesNotExist):
            get_exchange_rate(
                base_currency="EUR",
                target_currency="CZK",
                rate_date=date(2026, 10, 1),
            )

    def test_currency_pair_is_respected(self):
        """
        Проверяет, что сервис ищет именно указанную
        валютную пару, а не просто курс на дату.
        """

        ExchangeRate.objects.create(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("25.6410256410"),
            date=date(2026, 10, 3),
        )

        rate = get_exchange_rate(
            base_currency="CZK",
            target_currency="EUR",
            rate_date=date(2026, 10, 3),
        )

        self.assertEqual(
            rate,
            Decimal("0.0390000000"),
        )

class CurrencyConversionServiceTests(TestCase):
    """
    Тесты сервиса конвертации валют.
    """

    def setUp(self):
        """
        Создаёт исторические курсы
        для тестов конвертации.
        """

        ExchangeRate.objects.create(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("25.3164556962"),
            date=date(2026, 10, 6),
        )

        ExchangeRate.objects.create(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("25.0000000000"),
            date=date(2026, 10, 1),
        )

    def test_convert_currency(self):
        """
        Проверяет обычную конвертацию валюты.
        """

        result = convert_currency(
            amount=Decimal("100"),
            base_currency="EUR",
            target_currency="CZK",
            rate_date=date(2026, 10, 6),
        )

        self.assertEqual(
            result,
            Decimal("2531.65"),
        )

    def test_convert_currency_uses_historical_rate(self):
        """
        Проверяет, что используется курс,
        актуальный на дату операции.
        """

        result = convert_currency(
            amount=Decimal("100"),
            base_currency="EUR",
            target_currency="CZK",
            rate_date=date(2026, 10, 3),
        )

        self.assertEqual(
            result,
            Decimal("2500.00"),
        )

    def test_convert_currency_rounds_result(self):
        """
        Проверяет округление результата
        до двух знаков после запятой.
        """

        result = convert_currency(
            amount=Decimal("100"),
            base_currency="EUR",
            target_currency="CZK",
            rate_date=date(2026, 10, 6),
        )

        self.assertEqual(
            result.as_tuple().exponent,
            -2,
        )

    def test_convert_currency_with_custom_decimal_places(self):
        """
        Проверяет возможность изменить
        количество знаков после запятой.
        """

        result = convert_currency(
            amount=Decimal("100"),
            base_currency="EUR",
            target_currency="CZK",
            rate_date=date(2026, 10, 6),
            decimal_places=4,
        )

        self.assertEqual(
            result,
            Decimal("2531.6456"),
        )

    def test_same_currency_does_not_require_exchange_rate(self):
        """
        Проверяет конвертацию одинаковой валюты.

        Для CZK → CZK курс в ExchangeRate
        не требуется.
        """

        result = convert_currency(
            amount=Decimal("100.00"),
            base_currency="CZK",
            target_currency="CZK",
            rate_date=date(2026, 10, 6),
        )

        self.assertEqual(
            result,
            Decimal("100.00"),
        )

    def test_negative_amount_is_invalid(self):
        """
        Проверяет, что отрицательная сумма
        недопустима для конвертации.
        """

        with self.assertRaises(ValueError):
            convert_currency(
                amount=Decimal("-100"),
                base_currency="EUR",
                target_currency="CZK",
                rate_date=date(2026, 10, 6),
            )

    def test_negative_decimal_places_is_invalid(self):
        """
        Проверяет, что количество знаков
        после запятой не может быть отрицательным.
        """

        with self.assertRaises(ValueError):
            convert_currency(
                amount=Decimal("100"),
                base_currency="EUR",
                target_currency="CZK",
                rate_date=date(2026, 10, 6),
                decimal_places=-1,
            )

    def test_missing_exchange_rate_raises_error(self):
        """
        Проверяет ошибку, если исторический курс
        для указанной пары отсутствует.
        """

        with self.assertRaises(ExchangeRate.DoesNotExist):
            convert_currency(
                amount=Decimal("100"),
                base_currency="USD",
                target_currency="CZK",
                rate_date=date(2026, 10, 6),
            )

class ExpenseCurrencyConversionTests(TestCase):
    """
    Тесты конвертации суммы существующего Expense
    через Currency Service.
    """

    def setUp(self):
        """
        Создаёт пользователя, категорию, расход
        и исторический курс валюты.
        """

        self.user = User.objects.create_user(
            username="currencyuser",
            password="testpass123",
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Еда",
        )

        self.expense = Expense.objects.create(
            user=self.user,
            title="Ужин",
            amount=Decimal("100.00"),
            currency="EUR",
            category=self.category,
            date=date(2026, 10, 6),
        )

        ExchangeRate.objects.create(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("25.3164556962"),
            date=date(2026, 10, 6),
        )

    def test_convert_expense_amount(self):
        """
        Проверяет конвертацию существующего расхода
        из его валюты в целевую валюту.
        """

        result = convert_expense_amount(
            expense=self.expense,
            target_currency="CZK",
        )

        self.assertEqual(
            result,
            Decimal("2531.65"),
        )

    def test_expense_amount_is_not_changed(self):
        """
        Проверяет, что конвертация не изменяет
        исходную сумму Expense.
        """

        convert_expense_amount(
            expense=self.expense,
            target_currency="CZK",
        )

        self.assertEqual(
            self.expense.amount,
            Decimal("100.00"),
        )

    def test_expense_currency_is_not_changed(self):
        """
        Проверяет, что конвертация не изменяет
        исходную валюту Expense.
        """

        convert_expense_amount(
            expense=self.expense,
            target_currency="CZK",
        )

        self.assertEqual(
            self.expense.currency,
            "EUR",
        )

    def test_expense_date_is_used_for_rate_lookup(self):
        """
        Проверяет, что для конвертации используется
        дата самого расхода.
        """

        ExchangeRate.objects.create(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("30.0000000000"),
            date=date(2026, 10, 7),
        )

        result = convert_expense_amount(
            expense=self.expense,
            target_currency="CZK",
        )

        self.assertEqual(
            result,
            Decimal("2531.65"),
        )

    def test_same_currency_expense_does_not_require_rate(self):
        """
        Проверяет расход, который уже находится
        в целевой валюте.
        """

        self.expense.currency = "CZK"
        self.expense.amount = Decimal("500.00")

        result = convert_expense_amount(
            expense=self.expense,
            target_currency="CZK",
        )

        self.assertEqual(
            result,
            Decimal("500.00"),
        )

    def test_missing_rate_raises_error(self):
        """
        Проверяет ошибку при отсутствии
        подходящего исторического курса.
        """

        self.expense.currency = "USD"

        with self.assertRaises(ExchangeRate.DoesNotExist):
            convert_expense_amount(
                expense=self.expense,
                target_currency="CZK",
            )

class ExchangeRateDataTests(TestCase):
    """
    Проверяет нормализованный объект курса валюты,
    используемый между provider и внутренней системой.
    """

    def test_exchange_rate_data_creation(self):
        """
        Проверяет корректное создание ExchangeRateData.
        """

        rate_data = ExchangeRateData(
            base_currency="EUR",
            target_currency="CNY",
            rate=Decimal("7.4937"),
            date=date(2026, 10, 7),
        )

        self.assertEqual(
            rate_data.base_currency,
            "EUR",
        )

        self.assertEqual(
            rate_data.target_currency,
            "CNY",
        )

        self.assertEqual(
            rate_data.rate,
            Decimal("7.4937"),
        )

        self.assertEqual(
            rate_data.date,
            date(2026, 10, 7),
        )

    def test_exchange_rate_data_is_immutable(self):
        """
        Проверяет, что ExchangeRateData нельзя
        изменить после создания.
        """

        rate_data = ExchangeRateData(
            base_currency="EUR",
            target_currency="JPY",
            rate=Decimal("175.12"),
            date=date(2026, 10, 7),
        )

        with self.assertRaises(AttributeError):
            rate_data.rate = Decimal("180.00")


class ExchangeRateProviderTests(TestCase):
    """
    Проверяет базовый контракт ExchangeRateProvider
    и возможность создания его конкретной реализации.
    """

    def test_provider_is_abstract(self):
        """
        Проверяет, что базовый ExchangeRateProvider
        нельзя создать напрямую.
        """

        with self.assertRaises(TypeError):
            ExchangeRateProvider()

    def test_provider_requires_get_rates_implementation(self):
        """
        Проверяет, что конкретный provider обязан
        реализовать метод get_rates().
        """

        class IncompleteProvider(ExchangeRateProvider):
            pass

        with self.assertRaises(TypeError):
            IncompleteProvider()

    def test_provider_can_be_implemented(self):
        """
        Проверяет, что конкретный provider может
        реализовать контракт ExchangeRateProvider
        и вернуть нормализованные курсы.
        """

        class FakeExchangeRateProvider(
            ExchangeRateProvider
        ):
            def get_rates(
                self,
                rate_date,
            ):
                return [
                    ExchangeRateData(
                        base_currency="EUR",
                        target_currency="CNY",
                        rate=Decimal("7.4937"),
                        date=rate_date,
                    ),
                    ExchangeRateData(
                        base_currency="EUR",
                        target_currency="JPY",
                        rate=Decimal("175.12"),
                        date=rate_date,
                    ),
                ]

        provider = FakeExchangeRateProvider()

        rates = provider.get_rates(
            date(2026, 10, 7)
        )

        self.assertEqual(
            len(rates),
            2,
        )

        self.assertEqual(
            rates[0].base_currency,
            "EUR",
        )

        self.assertEqual(
            rates[0].target_currency,
            "CNY",
        )

        self.assertEqual(
            rates[0].rate,
            Decimal("7.4937"),
        )

        self.assertEqual(
            rates[1].base_currency,
            "EUR",
        )

        self.assertEqual(
            rates[1].target_currency,
            "JPY",
        )

        self.assertEqual(
            rates[1].rate,
            Decimal("175.12"),
        )

class ECBExchangeRateProviderTests(TestCase):
    """
    Проверяет конкретную реализацию provider
    для курсов Европейского центрального банка.
    """

    def test_provider_uses_fetcher(self):
        """
        Проверяет, что ECB provider использует
        переданную функцию получения курсов.
        """

        def fake_fetch_rates(rate_date):
            return {
                "CZK": Decimal("24.8500"),
                "USD": Decimal("1.1650"),
            }

        provider = ECBExchangeRateProvider(
            fetch_rates=fake_fetch_rates,
        )

        rates = provider.get_rates(
            date(2026, 10, 7)
        )

        self.assertEqual(len(rates), 2)

    def test_provider_returns_exchange_rate_data(self):
        """
        Проверяет, что ECB provider возвращает
        нормализованные объекты ExchangeRateData.
        """

        def fake_fetch_rates(rate_date):
            return {
                "CZK": Decimal("24.8500"),
            }

        provider = ECBExchangeRateProvider(
            fetch_rates=fake_fetch_rates,
        )

        rates = provider.get_rates(
            date(2026, 10, 7)
        )

        self.assertIsInstance(
            rates[0],
            ExchangeRateData,
        )

    def test_provider_uses_eur_as_base_currency(self):
        """
        Проверяет, что курсы ECB преобразуются
        в пары с EUR в качестве базовой валюты.
        """

        def fake_fetch_rates(rate_date):
            return {
                "CZK": Decimal("24.8500"),
                "USD": Decimal("1.1650"),
                "JPY": Decimal("175.1200"),
            }

        provider = ECBExchangeRateProvider(
            fetch_rates=fake_fetch_rates,
        )

        rates = provider.get_rates(
            date(2026, 10, 7)
        )

        for rate in rates:
            self.assertEqual(
                rate.base_currency,
                "EUR",
            )

    def test_provider_preserves_target_currencies(self):
        """
        Проверяет, что provider сохраняет
        коды целевых валют из источника.
        """

        def fake_fetch_rates(rate_date):
            return {
                "CZK": Decimal("24.8500"),
                "CNY": Decimal("7.4937"),
                "JPY": Decimal("175.1200"),
                "USD": Decimal("1.1650"),
            }

        provider = ECBExchangeRateProvider(
            fetch_rates=fake_fetch_rates,
        )

        rates = provider.get_rates(
            date(2026, 10, 7)
        )

        target_currencies = [
            rate.target_currency
            for rate in rates
        ]

        self.assertEqual(
            target_currencies,
            [
                "CZK",
                "CNY",
                "JPY",
                "USD",
            ],
        )

    def test_provider_preserves_decimal_rates(self):
        """
        Проверяет, что provider не преобразует
        Decimal в float и сохраняет точность курса.
        """

        def fake_fetch_rates(rate_date):
            return {
                "CNY": Decimal("7.4937"),
                "JPY": Decimal("175.1200"),
            }

        provider = ECBExchangeRateProvider(
            fetch_rates=fake_fetch_rates,
        )

        rates = provider.get_rates(
            date(2026, 10, 7)
        )

        self.assertEqual(
            rates[0].rate,
            Decimal("7.4937"),
        )

        self.assertEqual(
            rates[1].rate,
            Decimal("175.1200"),
        )

        self.assertIsInstance(
            rates[0].rate,
            Decimal,
        )

    def test_provider_uses_requested_date(self):
        """
        Проверяет, что дата, переданная provider,
        используется для всех возвращаемых курсов.
        """

        requested_date = date(2026, 10, 7)

        def fake_fetch_rates(rate_date):
            return {
                "CZK": Decimal("24.8500"),
            }

        provider = ECBExchangeRateProvider(
            fetch_rates=fake_fetch_rates,
        )

        rates = provider.get_rates(
            requested_date
        )

        self.assertEqual(
            rates[0].date,
            requested_date,
        )

    def test_provider_passes_requested_date_to_fetcher(self):
        """
        Проверяет, что provider передаёт запрошенную дату
        непосредственно функции получения курсов.
        """

        requested_date = date(2026, 10, 7)
        received_date = None

        def fake_fetch_rates(rate_date):
            nonlocal received_date

            received_date = rate_date

            return {
                "USD": Decimal("1.1650"),
            }

        provider = ECBExchangeRateProvider(
            fetch_rates=fake_fetch_rates,
        )

        provider.get_rates(requested_date)

        self.assertEqual(
            received_date,
            requested_date,
        )

    def test_provider_returns_empty_list_for_empty_source(self):
        """
        Проверяет корректную обработку ситуации,
        когда внешний источник не вернул ни одного курса.
        """

        def fake_fetch_rates(rate_date):
            return {}

        provider = ECBExchangeRateProvider(
            fetch_rates=fake_fetch_rates,
        )

        rates = provider.get_rates(
            date(2026, 10, 7)
        )

        self.assertEqual(
            rates,
            [],
        )

class ECBFetcherTests(TestCase):
    """
    Проверяет преобразование XML-ответа ECB
    в нормализованный словарь курсов валют.
    """

    def test_parse_ecb_rates(self):
        """
        Проверяет корректный разбор XML
        с несколькими валютами.
        """

        xml_content = """
        <Envelope>
            <Cube>
                <Cube time="2026-10-06">
                    <Cube currency="USD" rate="1.1269"/>
                    <Cube currency="JPY" rate="178.15"/>
                    <Cube currency="CZK" rate="24.405"/>
                    <Cube currency="CNY" rate="7.5554"/>
                </Cube>
            </Cube>
        </Envelope>
        """

        rates = parse_ecb_rates(xml_content)

        self.assertEqual(
            rates["USD"],
            Decimal("1.1269"),
        )

        self.assertEqual(
            rates["JPY"],
            Decimal("178.15"),
        )

        self.assertEqual(
            rates["CZK"],
            Decimal("24.405"),
        )

        self.assertEqual(
            rates["CNY"],
            Decimal("7.5554"),
        )

    def test_parse_ecb_rates_returns_decimal_values(self):
        """
        Проверяет, что значения курсов
        представлены типом Decimal.
        """

        xml_content = """
        <Envelope>
            <Cube>
                <Cube time="2026-10-06">
                    <Cube currency="USD" rate="1.1269"/>
                </Cube>
            </Cube>
        </Envelope>
        """

        rates = parse_ecb_rates(xml_content)

        self.assertIsInstance(
            rates["USD"],
            Decimal,
        )

    def test_parse_ecb_rates_preserves_precision(self):
        """
        Проверяет, что точность значения курса
        не теряется при парсинге XML.
        """

        xml_content = """
        <Envelope>
            <Cube>
                <Cube time="2026-10-06">
                    <Cube currency="CNY" rate="7.4937000000"/>
                </Cube>
            </Cube>
        </Envelope>
        """

        rates = parse_ecb_rates(xml_content)

        self.assertEqual(
            rates["CNY"],
            Decimal("7.4937000000"),
        )

    def test_parse_ecb_rates_ignores_non_rate_elements(self):
        """
        Проверяет, что элементы XML без currency
        или rate не попадают в результат.
        """

        xml_content = """
        <Envelope>
            <Cube>
                <Cube time="2026-10-06">
                    <Cube currency="USD" rate="1.1269"/>
                </Cube>
            </Cube>
        </Envelope>
        """

        rates = parse_ecb_rates(xml_content)

        self.assertEqual(
            len(rates),
            1,
        )

        self.assertIn(
            "USD",
            rates,
        )

    def test_parse_ecb_rates_returns_empty_dict_for_empty_xml(self):
        """
        Проверяет обработку XML,
        содержащего корректную структуру,
        но не содержащего курсов.
        """

        xml_content = """
        <Envelope>
            <Cube>
                <Cube time="2026-10-06"/>
            </Cube>
        </Envelope>
        """

        rates = parse_ecb_rates(xml_content)

        self.assertEqual(
            rates,
            {},
        )

    def test_parse_ecb_rates_supports_additional_currencies(self):
        """
        Проверяет, что parser не ограничен
        заранее заданным набором валют.

        Это важно для будущего добавления
        CNY, JPY, RUB и других валют.
        """

        xml_content = """
        <Envelope>
            <Cube>
                <Cube time="2026-10-06">
                    <Cube currency="AUD" rate="1.6140"/>
                    <Cube currency="CAD" rate="1.6058"/>
                    <Cube currency="INR" rate="108.6615"/>
                    <Cube currency="KRW" rate="1508.67"/>
                    <Cube currency="MXN" rate="20.2217"/>
                </Cube>
            </Cube>
        </Envelope>
        """

        rates = parse_ecb_rates(xml_content)

        self.assertEqual(
            rates["AUD"],
            Decimal("1.6140"),
        )

        self.assertEqual(
            rates["CAD"],
            Decimal("1.6058"),
        )

        self.assertEqual(
            rates["INR"],
            Decimal("108.6615"),
        )

        self.assertEqual(
            rates["KRW"],
            Decimal("1508.67"),
        )

        self.assertEqual(
            rates["MXN"],
            Decimal("20.2217"),
        )

class CBRFetcherTests(TestCase):
    """
    Проверяет парсинг XML-ответа
    Банка России.
    """

    def test_parse_multiple_currencies(self):
        """
        Проверяет корректный парсинг
        нескольких валют из XML.
        """

        xml_content = """<?xml version="1.0" encoding="windows-1251"?>
        <ValCurs Date="06.10.2026">
            <Valute>
                <CharCode>USD</CharCode>
                <Nominal>1</Nominal>
                <Value>80,5000</Value>
                <VunitRate>80,5000</VunitRate>
            </Valute>

            <Valute>
                <CharCode>EUR</CharCode>
                <Nominal>1</Nominal>
                <Value>94,2000</Value>
                <VunitRate>94,2000</VunitRate>
            </Valute>

            <Valute>
                <CharCode>CNY</CharCode>
                <Nominal>1</Nominal>
                <Value>11,1000</Value>
                <VunitRate>11,1000</VunitRate>
            </Valute>
        </ValCurs>
        """

        rates = parse_cbr_rates(
            xml_content
        )

        self.assertEqual(
            rates["USD"],
            Decimal("80.5000"),
        )

        self.assertEqual(
            rates["EUR"],
            Decimal("94.2000"),
        )

        self.assertEqual(
            rates["CNY"],
            Decimal("11.1000"),
        )

    def test_parse_returns_decimal_values(self):
        """
        Проверяет, что значения курсов
        представлены типом Decimal.
        """

        xml_content = """
        <ValCurs>
            <Valute>
                <CharCode>USD</CharCode>
                <VunitRate>80,5000</VunitRate>
            </Valute>
        </ValCurs>
        """

        rates = parse_cbr_rates(
            xml_content
        )

        self.assertIsInstance(
            rates["USD"],
            Decimal,
        )

    def test_parse_uses_vunit_rate(self):
        """
        Проверяет использование VunitRate
        вместо Value.

        VunitRate представляет курс
        одной единицы иностранной валюты
        к российскому рублю.
        """

        xml_content = """
        <ValCurs>
            <Valute>
                <CharCode>JPY</CharCode>
                <Nominal>100</Nominal>
                <Value>55,0000</Value>
                <VunitRate>0,5500</VunitRate>
            </Valute>
        </ValCurs>
        """

        rates = parse_cbr_rates(
            xml_content
        )

        self.assertEqual(
            rates["JPY"],
            Decimal("0.5500"),
        )

    def test_parse_supports_additional_currencies(self):
        """
        Проверяет, что parser не ограничивается
        заранее определённым набором валют.
        """

        xml_content = """
        <ValCurs>
            <Valute>
                <CharCode>USD</CharCode>
                <VunitRate>80,5000</VunitRate>
            </Valute>

            <Valute>
                <CharCode>EUR</CharCode>
                <VunitRate>94,2000</VunitRate>
            </Valute>

            <Valute>
                <CharCode>CNY</CharCode>
                <VunitRate>11,1000</VunitRate>
            </Valute>

            <Valute>
                <CharCode>JPY</CharCode>
                <VunitRate>0,5500</VunitRate>
            </Valute>
        </ValCurs>
        """

        rates = parse_cbr_rates(
            xml_content
        )

        self.assertEqual(
            set(rates.keys()),
            {"USD", "EUR", "CNY", "JPY"},
        )

    def test_parse_empty_xml(self):
        """
        Проверяет корректную обработку XML
        без валютных записей.
        """

        xml_content = """
        <ValCurs>
        </ValCurs>
        """

        rates = parse_cbr_rates(
            xml_content
        )

        self.assertEqual(
            rates,
            {},
        )

class CBRHTTPFetcherTests(TestCase):
    """
    Проверяет HTTP-слой получения курсов CBR.

    Реальные HTTP-запросы к Банку России
    в тестах не выполняются.
    """

    def setUp(self):
        """
        Создаёт тестовый XML-ответ CBR
        и дату запроса.
        """

        self.rate_date = date(2026, 10, 6)

        self.xml_content = """<?xml version="1.0" encoding="windows-1251"?>
        <ValCurs Date="06.10.2026"
                 name="Foreign Currency Market">
            <Valute ID="R01235">
                <NumCode>840</NumCode>
                <CharCode>USD</CharCode>
                <Nominal>1</Nominal>
                <Name>Доллар США</Name>
                <Value>80,5000</Value>
                <VunitRate>80,5000</VunitRate>
            </Valute>

            <Valute ID="R01239">
                <NumCode>978</NumCode>
                <CharCode>EUR</CharCode>
                <Nominal>1</Nominal>
                <Name>Евро</Name>
                <Value>94,2000</Value>
                <VunitRate>94,2000</VunitRate>
            </Valute>
        </ValCurs>
        """

    def test_fetcher_builds_correct_url(self):
        """
        Проверяет формирование URL
        с датой в формате DD/MM/YYYY.
        """

        calls = []

        class FakeResponse:
            """
            Имитирует HTTP-ответ Банка России.
            """

            def __enter__(self):
                return self

            def __exit__(
                self,
                exc_type,
                exc_value,
                traceback,
            ):
                return False

            def read(self):
                """
                Возвращает XML в кодировке
                windows-1251, как указано
                в XML-декларации.
                """

                return self.xml_content.encode(
                    "windows-1251"
                )

            xml_content = self.xml_content

        def fake_opener(request, timeout):
            """
            Имитирует urllib.request.urlopen.
            """

            calls.append(
                {
                    "url": request.full_url,
                    "timeout": timeout,
                }
            )

            return FakeResponse()

        fetch_cbr_rates(
            rate_date=self.rate_date,
            opener=fake_opener,
        )

        self.assertEqual(
            calls[0]["url"],
            (
                "https://www.cbr.ru/scripts/"
                "XML_daily.asp?date_req=06/10/2026"
            ),
        )

    def test_fetcher_uses_timeout(self):
        """
        Проверяет наличие таймаута
        при HTTP-запросе.
        """

        calls = []

        class FakeResponse:
            """
            Имитирует HTTP-ответ Банка России.
            """

            def __enter__(self):
                return self

            def __exit__(
                self,
                exc_type,
                exc_value,
                traceback,
            ):
                return False

            def read(self):
                """
                Возвращает XML в кодировке
                windows-1251.
                """

                return self.xml_content.encode(
                    "windows-1251"
                )

            xml_content = self.xml_content

        def fake_opener(request, timeout):
            """
            Имитирует HTTP-запрос
            и сохраняет переданный timeout.
            """

            calls.append(timeout)

            return FakeResponse()

        fetch_cbr_rates(
            rate_date=self.rate_date,
            opener=fake_opener,
        )

        self.assertEqual(
            calls,
            [10],
        )

    def test_fetcher_returns_parsed_rates(self):
        """
        Проверяет получение XML через HTTP
        и его последующий парсинг.
        """

        class FakeResponse:
            """
            Имитирует HTTP-ответ Банка России.
            """

            def __enter__(self):
                return self

            def __exit__(
                self,
                exc_type,
                exc_value,
                traceback,
            ):
                return False

            def read(self):
                """
                Возвращает XML в кодировке
                windows-1251.
                """

                return self.xml_content.encode(
                    "windows-1251"
                )

            xml_content = self.xml_content

        def fake_opener(request, timeout):
            """
            Возвращает тестовый HTTP-ответ.
            """

            return FakeResponse()

        rates = fetch_cbr_rates(
            rate_date=self.rate_date,
            opener=fake_opener,
        )

        self.assertEqual(
            rates["USD"],
            Decimal("80.5000"),
        )

        self.assertEqual(
            rates["EUR"],
            Decimal("94.2000"),
        )

    def test_fetcher_sets_user_agent(self):
        """
        Проверяет наличие User-Agent
        в HTTP-запросе.
        """

        calls = []

        class FakeResponse:
            """
            Имитирует HTTP-ответ Банка России.
            """

            def __enter__(self):
                return self

            def __exit__(
                self,
                exc_type,
                exc_value,
                traceback,
            ):
                return False

            def read(self):
                """
                Возвращает XML в кодировке
                windows-1251.
                """

                return self.xml_content.encode(
                    "windows-1251"
                )

            xml_content = self.xml_content

        def fake_opener(request, timeout):
            """
            Сохраняет HTTP-запрос
            для проверки его заголовков.
            """

            calls.append(request)

            return FakeResponse()

        fetch_cbr_rates(
            rate_date=self.rate_date,
            opener=fake_opener,
        )

        self.assertEqual(
            calls[0].headers["User-agent"],
            "finance-tracker/1.0",
        )

class CBRExchangeRateProviderTests(TestCase):
    """
    Проверяет работу provider курсов
    Центрального банка России.
    """

    def setUp(self):
        """
        Создаёт тестовые курсы CBR
        и дату для provider.
        """

        self.rate_date = date(2026, 10, 6)

        self.source_rates = {
            "USD": Decimal("80.50"),
            "EUR": Decimal("94.20"),
            "CNY": Decimal("11.10"),
            "JPY": Decimal("0.55"),
        }

    def test_provider_uses_fetcher(self):
        """
        Проверяет, что provider использует
        переданную функцию получения курсов.
        """

        calls = []

        def fetch_rates(rate_date):
            calls.append(rate_date)
            return self.source_rates

        provider = CBRExchangeRateProvider(
            fetch_rates=fetch_rates,
        )

        provider.get_rates(self.rate_date)

        self.assertEqual(
            calls,
            [self.rate_date],
        )

    def test_provider_returns_exchange_rate_data(self):
        """
        Проверяет, что provider возвращает
        объекты ExchangeRateData.
        """

        provider = CBRExchangeRateProvider(
            fetch_rates=lambda rate_date: self.source_rates,
        )

        rates = provider.get_rates(self.rate_date)

        self.assertTrue(
            all(
                isinstance(rate, ExchangeRateData)
                for rate in rates
            )
        )

    def test_provider_uses_rub_as_target_currency(self):
        """
        Проверяет, что RUB используется
        как целевая валюта.
        """

        provider = CBRExchangeRateProvider(
            fetch_rates=lambda rate_date: self.source_rates,
        )

        rates = provider.get_rates(self.rate_date)

        self.assertTrue(
            all(
                rate.target_currency == "RUB"
                for rate in rates
            )
        )

    def test_provider_preserves_source_currencies(self):
        """
        Проверяет сохранение кодов валют,
        полученных от CBR.
        """

        provider = CBRExchangeRateProvider(
            fetch_rates=lambda rate_date: self.source_rates,
        )

        rates = provider.get_rates(self.rate_date)

        currencies = {
            rate.base_currency
            for rate in rates
        }

        self.assertEqual(
            currencies,
            {"USD", "EUR", "CNY", "JPY"},
        )

    def test_provider_preserves_decimal_rates(self):
        """
        Проверяет, что provider сохраняет курсы
        в формате Decimal.
        """

        provider = CBRExchangeRateProvider(
            fetch_rates=lambda rate_date: self.source_rates,
        )

        rates = provider.get_rates(self.rate_date)

        self.assertTrue(
            all(
                isinstance(rate.rate, Decimal)
                for rate in rates
            )
        )

    def test_provider_preserves_rate_values(self):
        """
        Проверяет сохранение точных значений
        курсов CBR.
        """

        provider = CBRExchangeRateProvider(
            fetch_rates=lambda rate_date: self.source_rates,
        )

        rates = provider.get_rates(self.rate_date)

        rates_by_currency = {
            rate.base_currency: rate.rate
            for rate in rates
        }

        self.assertEqual(
            rates_by_currency["USD"],
            Decimal("80.50"),
        )

        self.assertEqual(
            rates_by_currency["EUR"],
            Decimal("94.20"),
        )

        self.assertEqual(
            rates_by_currency["CNY"],
            Decimal("11.10"),
        )

    def test_provider_preserves_requested_date(self):
        """
        Проверяет, что provider использует
        переданную дату курса.
        """

        provider = CBRExchangeRateProvider(
            fetch_rates=lambda rate_date: self.source_rates,
        )

        rates = provider.get_rates(self.rate_date)

        self.assertTrue(
            all(
                rate.date == self.rate_date
                for rate in rates
            )
        )

    def test_empty_source_returns_empty_list(self):
        """
        Проверяет корректную обработку ситуации,
        когда источник не вернул курсы.
        """

        provider = CBRExchangeRateProvider(
            fetch_rates=lambda rate_date: {},
        )

        rates = provider.get_rates(self.rate_date)

        self.assertEqual(
            rates,
            [],
        )


class RateUpdaterTests(TestCase):
    """
    Проверяет persistence и validation слоя RateUpdater.
    """

    def setUp(self):
        """
        Создаёт updater и общую дату
        для тестов.
        """

        self.updater = RateUpdater()
        self.rate_date = date(2026, 10, 7)

    def test_update_creates_exchange_rate(self):
        """
        Проверяет создание нового курса.
        """

        rate_data = ExchangeRateData(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("24.4050000000"),
            date=self.rate_date,
        )

        result = self.updater.update([rate_data])

        self.assertEqual(result, 1)

        exchange_rate = ExchangeRate.objects.get(
            base_currency="EUR",
            target_currency="CZK",
            date=self.rate_date,
        )

        self.assertEqual(
            exchange_rate.rate,
            Decimal("24.4050000000"),
        )

    def test_update_creates_multiple_exchange_rates(self):
        """
        Проверяет сохранение нескольких курсов
        за один вызов.
        """

        rates = [
            ExchangeRateData(
                base_currency="EUR",
                target_currency="CZK",
                rate=Decimal("24.4050000000"),
                date=self.rate_date,
            ),
            ExchangeRateData(
                base_currency="EUR",
                target_currency="USD",
                rate=Decimal("1.1650000000"),
                date=self.rate_date,
            ),
            ExchangeRateData(
                base_currency="USD",
                target_currency="RUB",
                rate=Decimal("80.5000000000"),
                date=self.rate_date,
            ),
        ]

        result = self.updater.update(rates)

        self.assertEqual(result, 3)
        self.assertEqual(
            ExchangeRate.objects.count(),
            3,
        )

    def test_update_returns_zero_for_empty_iterable(self):
        """
        Проверяет обработку пустого набора курсов.
        """

        result = self.updater.update([])

        self.assertEqual(result, 0)

        self.assertEqual(
            ExchangeRate.objects.count(),
            0,
        )

    def test_update_accepts_generator(self):
        """
        Проверяет, что updater работает не только
        со списком, но и с любым Iterable.
        """

        def generate_rates():
            yield ExchangeRateData(
                base_currency="EUR",
                target_currency="CZK",
                rate=Decimal("24.4050000000"),
                date=self.rate_date,
            )
            yield ExchangeRateData(
                base_currency="EUR",
                target_currency="USD",
                rate=Decimal("1.1650000000"),
                date=self.rate_date,
            )

        result = self.updater.update(
            generate_rates()
        )

        self.assertEqual(result, 2)
        self.assertEqual(
            ExchangeRate.objects.count(),
            2,
        )

    def test_update_updates_existing_rate(self):
        """
        Проверяет обновление существующего курса
        для той же пары валют и даты.
        """

        ExchangeRate.objects.create(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("24.0000000000"),
            date=self.rate_date,
        )

        rate_data = ExchangeRateData(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("24.4050000000"),
            date=self.rate_date,
        )

        result = self.updater.update([rate_data])

        self.assertEqual(result, 1)

        self.assertEqual(
            ExchangeRate.objects.count(),
            1,
        )

        exchange_rate = ExchangeRate.objects.get(
            base_currency="EUR",
            target_currency="CZK",
            date=self.rate_date,
        )

        self.assertEqual(
            exchange_rate.rate,
            Decimal("24.4050000000"),
        )

    def test_update_is_idempotent(self):
        """
        Проверяет идемпотентность повторного запуска
        с одинаковыми данными.
        """

        rate_data = ExchangeRateData(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("24.4050000000"),
            date=self.rate_date,
        )

        first_result = self.updater.update([rate_data])
        second_result = self.updater.update([rate_data])

        self.assertEqual(first_result, 1)
        self.assertEqual(second_result, 1)

        self.assertEqual(
            ExchangeRate.objects.count(),
            1,
        )

    def test_update_rejects_unsupported_base_currency(self):
        """
        Проверяет отклонение неизвестной базовой валюты.
        """

        rate_data = ExchangeRateData(
            base_currency="XXX",
            target_currency="CZK",
            rate=Decimal("24.4050000000"),
            date=self.rate_date,
        )

        with self.assertRaisesMessage(
            ValueError,
            "Unsupported base currency: XXX",
        ):
            self.updater.update([rate_data])

        self.assertEqual(
            ExchangeRate.objects.count(),
            0,
        )

    def test_update_rejects_unsupported_target_currency(self):
        """
        Проверяет отклонение неизвестной целевой валюты.
        """

        rate_data = ExchangeRateData(
            base_currency="EUR",
            target_currency="XXX",
            rate=Decimal("24.4050000000"),
            date=self.rate_date,
        )

        with self.assertRaisesMessage(
            ValueError,
            "Unsupported target currency: XXX",
        ):
            self.updater.update([rate_data])

        self.assertEqual(
            ExchangeRate.objects.count(),
            0,
        )

    def test_update_rejects_same_currencies(self):
        """
        Проверяет запрет курса валюты самой к себе.
        """

        rate_data = ExchangeRateData(
            base_currency="EUR",
            target_currency="EUR",
            rate=Decimal("1.0000000000"),
            date=self.rate_date,
        )

        with self.assertRaisesMessage(
            ValueError,
            "Base and target currencies must be different.",
        ):
            self.updater.update([rate_data])

        self.assertEqual(
            ExchangeRate.objects.count(),
            0,
        )

    def test_update_rejects_zero_rate(self):
        """
        Проверяет запрет нулевого курса.
        """

        rate_data = ExchangeRateData(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("0"),
            date=self.rate_date,
        )

        with self.assertRaisesMessage(
            ValueError,
            "Exchange rate must be positive.",
        ):
            self.updater.update([rate_data])

        self.assertEqual(
            ExchangeRate.objects.count(),
            0,
        )

    def test_update_rejects_negative_rate(self):
        """
        Проверяет запрет отрицательного курса.
        """

        rate_data = ExchangeRateData(
            base_currency="EUR",
            target_currency="CZK",
            rate=Decimal("-1.0000000000"),
            date=self.rate_date,
        )

        with self.assertRaisesMessage(
            ValueError,
            "Exchange rate must be positive.",
        ):
            self.updater.update([rate_data])

        self.assertEqual(
            ExchangeRate.objects.count(),
            0,
        )

    def test_update_rolls_back_all_changes_on_validation_error(self):
        """
        Проверяет атомарность batch-операции.

        Если один курс в batch невалиден,
        ранее сохранённые курсы также откатываются.
        """

        rates = [
            ExchangeRateData(
                base_currency="EUR",
                target_currency="CZK",
                rate=Decimal("24.4050000000"),
                date=self.rate_date,
            ),
            ExchangeRateData(
                base_currency="EUR",
                target_currency="XXX",
                rate=Decimal("1.0000000000"),
                date=self.rate_date,
            ),
        ]

        with self.assertRaisesMessage(
            ValueError,
            "Unsupported target currency: XXX",
        ):
            self.updater.update(rates)

        self.assertEqual(
            ExchangeRate.objects.count(),
            0,
        )

    def test_update_rolls_back_all_changes_when_later_rate_is_invalid(self):
        """
        Проверяет, что rollback происходит для всего batch,
        даже если ошибка возникает после нескольких
        успешно обработанных курсов.
        """

        rates = [
            ExchangeRateData(
                base_currency="EUR",
                target_currency="CZK",
                rate=Decimal("24.4050000000"),
                date=self.rate_date,
            ),
            ExchangeRateData(
                base_currency="EUR",
                target_currency="USD",
                rate=Decimal("1.1650000000"),
                date=self.rate_date,
            ),
            ExchangeRateData(
                base_currency="EUR",
                target_currency="EUR",
                rate=Decimal("1.0000000000"),
                date=self.rate_date,
            ),
        ]

        with self.assertRaisesMessage(
            ValueError,
            "Base and target currencies must be different.",
        ):
            self.updater.update(rates)

        self.assertEqual(
            ExchangeRate.objects.count(),
            0,
        )
