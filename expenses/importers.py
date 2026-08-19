import csv
import io

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Category
from .services import create_expense


REQUIRED_COLUMNS = {
    "date",
    "title",
    "category",
    "amount",
    "description",
}


class ExpenseCSVImporter:

    def __init__(self, *, user):
        self.user = user

    @transaction.atomic
    def import_file(self, file):
        created = 0
        errors = []

        # Проверяем кодировку CSV
        try:
            content = file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return {
                "created": 0,
                "errors": [
                    {
                        "row": 1,
                        "error": "CSV file must be encoded in UTF-8.",
                    }
                ],
            }

        reader = csv.DictReader(io.StringIO(content))

        # Проверяем, что CSV содержит заголовки
        if not reader.fieldnames:
            return {
                "created": 0,
                "errors": [
                    {
                        "row": 1,
                        "error": "CSV file is empty.",
                    }
                ],
            }

        # Проверяем обязательные колонки
        columns = {
            column.strip()
            for column in reader.fieldnames
        }

        missing_columns = REQUIRED_COLUMNS - columns

        if missing_columns:
            return {
                "created": 0,
                "errors": [
                    {
                        "row": 1,
                        "error": (
                            "Missing required columns: "
                            + ", ".join(sorted(missing_columns))
                        ),
                    }
                ],
            }

        # Обрабатываем строки CSV
        for row_number, row in enumerate(reader, start=2):

            try:
                title = row.get("title", "").strip()
                category_name = row.get("category", "").strip()
                amount = row.get("amount", "").strip()
                date = row.get("date", "").strip()
                description = row.get("description", "").strip()

                # Проверяем обязательные значения
                if not title:
                    raise ValidationError(
                        "Title is required."
                    )

                if not category_name:
                    raise ValidationError(
                        "Category is required."
                    )

                if not amount:
                    raise ValidationError(
                        "Amount is required."
                    )

                if not date:
                    raise ValidationError(
                        "Date is required."
                    )

                # Ищем категорию только текущего пользователя
                category = Category.objects.filter(
                    user=self.user,
                    name=category_name,
                ).first()

                if category is None:
                    raise ValidationError(
                        f"Category '{category_name}' does not exist."
                    )

                # Создаём расход через service
                create_expense(
                    user=self.user,
                    title=title,
                    amount=amount,
                    category=category,
                    date=date,
                    description=description,
                )

                created += 1

            except (
                ValidationError,
                ValueError,
                TypeError,
            ) as exc:

                if hasattr(exc, "messages"):
                    error_message = exc.messages[0]
                else:
                    error_message = str(exc)

                errors.append(
                    {
                        "row": row_number,
                        "error": error_message,
                    }
                )

        return {
            "created": created,
            "errors": errors,
        }
    