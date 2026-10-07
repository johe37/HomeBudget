from __future__ import annotations

import re

from .calc import derived_lines, summarize
from .constants import MANUAL
from .models import Expense, Plan

_TRAILING_COPY = re.compile(r"\s+kopia(?:\s+\d+)?$")


def name_taken(user, name: str, exclude_pk=None) -> bool:
    existing = Plan.objects.filter(user=user, name__iexact=name)
    if exclude_pk is not None:
        existing = existing.exclude(pk=exclude_pk)
    return existing.exists()


def suggested_copy_name(user, source_name: str) -> str:
    stem = _copy_stem(source_name)
    suffix = " kopia"
    base = f"{stem[: 80 - len(suffix)].rstrip()}{suffix}"
    candidate = base
    number = 2
    while name_taken(user, candidate):
        extra = f" {number}"
        room = 80 - len(extra)
        head = base[:room].rstrip() if room > 0 else ""
        candidate = f"{head}{extra}"[:80]
        number += 1
    return candidate


def _copy_stem(source_name: str) -> str:
    stem = source_name.strip()
    while stem:
        shortened = _TRAILING_COPY.sub("", stem).strip()
        if not shortened or shortened == stem:
            return stem
        stem = shortened
    return source_name.strip()


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


def create_empty_plan(user, name: str) -> Plan:
    plan = Plan.objects.create(user=user, name=name)
    sync_derived(plan)
    return plan


def clone_plan(source: Plan, name: str) -> Plan:
    clone = Plan.objects.create(
        user=source.user,
        name=name,
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
