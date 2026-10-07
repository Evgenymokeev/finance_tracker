from decimal import Decimal
from xml.etree import ElementTree


def parse_cbr_rates(
    xml_content: str,
) -> dict[str, Decimal]:
    """
    Преобразует XML-ответ Банка России
    в словарь курсов валют.

    Банк России публикует курс иностранной валюты
    относительно российского рубля.

    Например:

        USD
        VunitRate = 80.50

    означает:

        1 USD = 80.50 RUB

    Результат:

        {
            "USD": Decimal("80.50")
        }

    Функция занимается только парсингом XML.
    HTTP-запросы выполняются отдельным слоем.
    """

    root = ElementTree.fromstring(xml_content)

    rates = {}

    for item in root.iter("Valute"):
        currency = item.findtext("CharCode")
        unit_rate = item.findtext("VunitRate")

        if currency is None or unit_rate is None:
            continue

        rates[currency] = Decimal(
            unit_rate.replace(",", ".")
        )

    return rates