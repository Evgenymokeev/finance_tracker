from datetime import date

from celery import shared_task
from django.utils import timezone

from .providers.factory import get_exchange_rate_provider
from .rate_service import RateService


@shared_task(
    name="currency.tasks.update_exchange_rates",
)
def update_exchange_rates(
    source: str,
    rate_date: str | None = None,
) -> dict:
    """
    Обновляет курсы валют из выбранного источника.

    Задача координирует выполнение фонового обновления:
    выбирает дату, создаёт Provider и запускает RateService.

    Args:
        source: Идентификатор источника — ecb или cbr.
        rate_date: Дата в формате YYYY-MM-DD.
            Если дата не передана, используется текущая дата.

    Returns:
        Словарь с источником, датой и количеством обработанных курсов.

    Raises:
        ValueError: Если передана некорректная дата
            или неизвестный источник.
        Исключения Provider и RateService передаются Celery,
        чтобы ошибка не маскировалась под успешное обновление.
    """

    if rate_date is None:
        selected_date = timezone.localdate()
    else:
        try:
            selected_date = date.fromisoformat(rate_date)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "rate_date must be in YYYY-MM-DD format"
            ) from error

        if selected_date.isoformat() != rate_date:
            raise ValueError(
                "rate_date must be in YYYY-MM-DD format"
            )

    provider = get_exchange_rate_provider(source)
    service = RateService(provider=provider)

    processed = service.update_rates(selected_date)

    return {
        "source": source.lower(),
        "date": selected_date.isoformat(),
        "processed": processed,
    }