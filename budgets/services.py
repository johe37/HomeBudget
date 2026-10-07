from __future__ import annotations

from .calc import derived_lines, summarize
from .constants import MANUAL, SWEDISH_MONTHS
from .models import Expense, Plan


def month_title(year: int, month: int) -> str:
    return f"{SWEDISH_MONTHS[month]} {year}"


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def next_open_month(user) -> tuple[int, int]:
    latest = Plan.objects.filter(user=user).order_by("-year", "-month").first()
    if latest is None:
        from datetime import date

        today = date.today()
        return today.year, today.month
    return next_month(latest.year, latest.month)


def sync_derived(plan: Plan) -> None:
    lines = derived_lines(plan)
    keep = set()
    for index, line in enumerate(lines):
        keep.add(line.source)
        Expense.objects.update_or_create(
            plan=plan,
            source=line.source,
            defaults={
                "name": line.name,
                "category": line.category,
                "person": line.person,
                "amount": line.amount,
                "note": line.note,
                "active": True,
                "sort_order": index,
            },
        )
    plan.expenses.exclude(source=MANUAL).exclude(source__in=keep).delete()


def summarize_plan(plan: Plan):
    return summarize(
        plan,
        list(plan.incomes.all()),
        list(plan.expenses.all()),
    )


def create_empty_plan(user, year: int, month: int) -> Plan:
    plan = Plan.objects.create(user=user, year=year, month=month)
    sync_derived(plan)
    return plan


def clone_plan(source: Plan, year: int, month: int) -> Plan:
    clone = Plan.objects.create(
        user=source.user,
        year=year,
        month=month,
        note=source.note,
        mortgage_balance=source.mortgage_balance,
        mortgage_rate=source.mortgage_rate,
        amortization_rate=source.amortization_rate,
    )
    for income in source.incomes.all():
        income.pk = None
        income.plan = clone
        income.save()
    for expense in source.expenses.filter(source=MANUAL):
        expense.pk = None
        expense.plan = clone
        expense.save()
    sync_derived(clone)
    return clone
