from __future__ import annotations

import json
import re
from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from .calc import derived_lines, ore, rate_from_micro, scale_ore, summarize
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


def _percent_map(raw: str) -> dict[str, int]:
    if not (raw or "").strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("percent map")
    cleaned = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            raise ValueError("percent key")
        number = int(value)
        cleaned[key] = max(0, min(number, 200))
    return cleaned


def _micro(raw: str) -> int:
    return max(0, min(int(raw), 1_000_000))


def _money_from_ore(amount_ore: int) -> Decimal:
    return Decimal(amount_ore) / Decimal(100)


def _scale_rows(rows, attr: str, percent: int) -> None:
    if percent == 100 or not rows:
        return
    original = [ore(getattr(row, attr)) for row in rows]
    target = scale_ore(sum(original), percent)
    scaled = [scale_ore(amount, percent) for amount in original]
    scaled[-1] += target - sum(scaled)
    for row, amount_ore in zip(rows, scaled):
        setattr(row, attr, _money_from_ore(amount_ore))
        row.save(update_fields=[attr])


def save_tried_plan(source: Plan, rate_raw: str, amort_raw: str, income_raw: str, expense_raw: str) -> Plan:
    """Copy source and apply the Om sliders. The source budget is left as saved."""
    income_scale = _percent_map(income_raw)
    expense_scale = _percent_map(expense_raw)
    with transaction.atomic():
        clone = clone_plan(source, suggested_copy_name(source.user, source.name))
        clone.mortgage_rate = rate_from_micro(_micro(rate_raw))
        clone.amortization_rate = rate_from_micro(_micro(amort_raw))
        clone.save(update_fields=["mortgage_rate", "amortization_rate"])

        incomes: dict[str, list] = defaultdict(list)
        for income in clone.incomes.all():
            if income.active:
                incomes[income.person or ""].append(income)
        for person, rows in incomes.items():
            _scale_rows(rows, "net", income_scale.get(person, 100))

        expenses: dict[str, list] = defaultdict(list)
        for expense in clone.expenses.filter(source=MANUAL):
            if expense.active:
                expenses[(expense.category or "").strip()].append(expense)
        for category, rows in expenses.items():
            _scale_rows(rows, "amount", expense_scale.get(category, 100))

        sync_derived(clone)
    return clone


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
