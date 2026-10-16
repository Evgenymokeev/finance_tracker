from .base import ExchangeRateProvider
from .cbr import CBRExchangeRateProvider
from .cbr_http import fetch_cbr_rates
from .ecb import ECBExchangeRateProvider
from .ecb_http import fetch_ecb_rates


def get_exchange_rate_provider(
    source: str,
) -> ExchangeRateProvider:
    """
    Создаёт Provider для выбранного источника курсов.

    Фабрика отделяет конфигурацию источников от Celery-задачи.
    Каждый Provider получает реальную функцию загрузки данных.

    Args:
        source: Идентификатор источника — ecb или cbr.

    Returns:
        Настроенный Provider для выбранного источника.

    Raises:
        ValueError: Если источник не поддерживается.
    """

    providers = {
        "ecb": lambda: ECBExchangeRateProvider(
            fetch_rates=fetch_ecb_rates,
        ),
        "cbr": lambda: CBRExchangeRateProvider(
            fetch_rates=fetch_cbr_rates,
        ),
    }

    provider_factory = providers.get(source.lower())

    if provider_factory is None:
        raise ValueError(
            f"Unsupported exchange rate source: {source}"
        )

    return provider_factory()