from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Category


User = get_user_model()


DEFAULT_CATEGORIES = [
    "Еда",
    "Транспорт",
    "Дом",
    "Развлечения",
    "Здоровье",
]


@receiver(post_save, sender=User)
def create_default_categories(sender, instance, created, **kwargs):

    if created:
        Category.objects.bulk_create(
            [
                Category(
                    user=instance,
                    name=name
                )
                for name in DEFAULT_CATEGORIES
            ]
        )