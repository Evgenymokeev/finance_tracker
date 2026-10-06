from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from categories.models import Category
from expenses.models import Expense

from .models import ExchangeRate
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
