from django.contrib import admin

from .models import Debt, Expense, OffSiteSale, OffSiteSaleMeal, OffSiteSaleSupplement


class OffSiteSaleMealInline(admin.TabularInline):
    model = OffSiteSaleMeal
    extra = 0


class OffSiteSaleSupplementInline(admin.TabularInline):
    model = OffSiteSaleSupplement
    extra = 0


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("date", "category", "description", "amount")
    list_filter = ("category", "date")
    search_fields = ("description", "notes")
    date_hierarchy = "date"


@admin.register(OffSiteSale)
class OffSiteSaleAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "amount", "payment_method")
    list_filter = ("payment_method", "date")
    search_fields = ("description", "notes")
    date_hierarchy = "date"
    inlines = (OffSiteSaleMealInline, OffSiteSaleSupplementInline)


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "user", "debt_type", "amount", "is_paid", "due_date")
    list_filter = ("debt_type", "is_paid", "date", "due_date")
    search_fields = ("description", "reason", "user__username", "user__email")
    date_hierarchy = "date"
