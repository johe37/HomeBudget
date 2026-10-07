from django.contrib import admin

from .models import Expense, Income, Plan


class IncomeInline(admin.TabularInline):
    model = Income
    extra = 0


class ExpenseInline(admin.TabularInline):
    model = Expense
    extra = 0


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "updated_at")
    list_filter = ("year",)
    inlines = [IncomeInline, ExpenseInline]
