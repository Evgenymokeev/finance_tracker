from datetime import datetime

from django.test import SimpleTestCase

from goals.models import GoalAutomaticSaving

from goals.services import calculate_next_run_at


class CalculateNextRunAtTests(SimpleTestCase):
    """
    Тесты расчёта следующего запуска Automatic Saving.
    """

    def test_daily(self):
        """
        daily -> +1 день.
        """

        current = datetime(
            2026,
            9,
            12,
            9,
            0,
        )

        result = calculate_next_run_at(
            current,
            GoalAutomaticSaving.Frequency.DAILY,
        )

        self.assertEqual(
            result,
            datetime(
                2026,
                9,
                13,
                9,
                0,
            ),
        )

    def test_weekly(self):
        """
        weekly -> +7 дней.
        """

        current = datetime(
            2026,
            9,
            12,
            9,
            0,
        )

        result = calculate_next_run_at(
            current,
            GoalAutomaticSaving.Frequency.WEEKLY,
        )

        self.assertEqual(
            result,
            datetime(
                2026,
                9,
                19,
                9,
                0,
            ),
        )

    def test_monthly(self):
        """
        monthly -> следующий месяц.
        """

        current = datetime(
            2026,
            9,
            12,
            9,
            0,
        )

        result = calculate_next_run_at(
            current,
            GoalAutomaticSaving.Frequency.MONTHLY,
        )

        self.assertEqual(
            result,
            datetime(
                2026,
                10,
                12,
                9,
                0,
            ),
        )

    def test_monthly_from_end_of_month(self):
        """
        31 января -> 28 февраля.
        """

        current = datetime(
            2026,
            1,
            31,
            9,
            0,
        )

        result = calculate_next_run_at(
            current,
            GoalAutomaticSaving.Frequency.MONTHLY,
        )

        self.assertEqual(
            result,
            datetime(
                2026,
                2,
                28,
                9,
                0,
            ),
        )

    def test_yearly(self):
        """
        yearly -> следующий год.
        """

        current = datetime(
            2026,
            9,
            12,
            9,
            0,
        )

        result = calculate_next_run_at(
            current,
            GoalAutomaticSaving.Frequency.YEARLY,
        )

        self.assertEqual(
            result,
            datetime(
                2027,
                9,
                12,
                9,
                0,
            ),
        )

    def test_yearly_from_leap_day(self):
        """
        29 февраля -> 28 февраля следующего года.
        """

        current = datetime(
            2028,
            2,
            29,
            9,
            0,
        )

        result = calculate_next_run_at(
            current,
            GoalAutomaticSaving.Frequency.YEARLY,
        )

        self.assertEqual(
            result,
            datetime(
                2029,
                2,
                28,
                9,
                0,
            ),
        )

    def test_custom(self):
        """
        custom + interval 14 -> +14 дней.
        """

        current = datetime(
            2026,
            9,
            12,
            9,
            0,
        )

        result = calculate_next_run_at(
            current,
            GoalAutomaticSaving.Frequency.CUSTOM,
            interval=14,
        )

        self.assertEqual(
            result,
            datetime(
                2026,
                9,
                26,
                9,
                0,
            ),
        )

    def test_custom_requires_interval(self):
        """
        custom без interval вызывает ошибку.
        """

        current = datetime(
            2026,
            9,
            12,
            9,
            0,
        )

        with self.assertRaises(ValueError):
            calculate_next_run_at(
                current,
                GoalAutomaticSaving.Frequency.CUSTOM,
            )

    def test_custom_interval_must_be_positive(self):
        """
        custom с interval <= 0 вызывает ошибку.
        """

        current = datetime(
            2026,
            9,
            12,
            9,
            0,
        )

        with self.assertRaises(ValueError):
            calculate_next_run_at(
                current,
                GoalAutomaticSaving.Frequency.CUSTOM,
                interval=0,
            )

    def test_unsupported_frequency(self):
        """
        Неизвестная frequency вызывает ошибку.
        """

        current = datetime(
            2026,
            9,
            12,
            9,
            0,
        )

        with self.assertRaises(ValueError):
            calculate_next_run_at(
                current,
                "unknown",
            )
