from datetime import date

from .providers.base import ExchangeRateProvider
from .rate_updater import RateUpdater


class RateService:
    """
    Координирует получение и обновление курсов валют.

    Provider отвечает за получение и нормализацию данных.
    RateUpdater отвечает за валидацию и сохранение курсов.
    RateService связывает эти компоненты в единый процесс.
    """

    def __init__(
        self,
        provider: ExchangeRateProvider,
        updater: RateUpdater | None = None,
    ) -> None:
        """
        Инициализирует сервис обновления курсов валют.

        Args:
            provider: Источник курсов валют.
            updater: Компонент валидации и сохранения курсов.
                Если не передан, создаётся стандартный RateUpdater.
        """

        self.provider = provider
        self.updater = (
            updater if updater is not None else RateUpdater()
        )

    def update_rates(self, rate_date: date) -> int:
        """
        Получает курсы на указанную дату и передаёт их на сохранение.

        Args:
            rate_date: Дата, на которую необходимо получить курсы.

        Returns:
            Количество обработанных курсов.

        Raises:
            Исключения Provider, если получение данных завершилось
            ошибкой.
            Исключения RateUpdater, если валидация или сохранение
            курсов завершились ошибкой.
        """

        rates = self.provider.get_rates(rate_date)

        return self.updater.update(rates)
