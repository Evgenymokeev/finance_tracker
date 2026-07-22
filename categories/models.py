from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="categories"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Название категории"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )


    class Meta:
     ordering = ["name"]

    verbose_name = "Категория"
    verbose_name_plural = "Категории"

    constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_user_category"
            )
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip().capitalize()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.user.username})"
# Create your models here.
