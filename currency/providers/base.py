from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ExchangeRateData:
    """
    Нормализованный курс валюты,
    полученный от внешнего источника.
    """

    base_currency: str
    target_currency: str
    rate: Decimal
    date: date


class ExchangeRateProvider(ABC):
    """
    Базовый интерфейс источника курсов валют.

    Конкретная реализация отвечает только за получение
    и нормализацию данных внешнего источника.
    """

    @abstractmethod
    def get_rates(
        self,
        rate_date: date,
    ) -> list[ExchangeRateData]:
        """
        Возвращает доступные курсы на указанную дату.
        """
        raise NotImplementedError