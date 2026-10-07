from datetime import date
from decimal import Decimal
from xml.etree import ElementTree


def parse_ecb_rates(
    xml_content: str,
) -> dict[str, Decimal]:
    """
    Преобразует XML-ответ ECB
    в словарь курсов валют.

    ECB публикует reference rates относительно EUR.

    Например:

        <Cube currency="CZK" rate="24.405"/>

    преобразуется в:

        {
            "CZK": Decimal("24.405")
        }

    Функция занимается только парсингом XML
    и не выполняет HTTP-запросы.
    """

    root = ElementTree.fromstring(xml_content)

    rates = {}

    for cube in root.iter():
        currency = cube.attrib.get("currency")
        rate = cube.attrib.get("rate")

        if currency is None or rate is None:
            continue

        rates[currency] = Decimal(rate)

    return rates