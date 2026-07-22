from django.contrib import admin
from .models import Expense
from .models import Expense, Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
    )

    search_fields = (
        "name",
    )

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "amount",
        "category",
        "date",
    )

    search_fields = (
        "title",
        "category",
    )

    list_filter = (
        "category",
        "date",
    )

# Register your models here.
