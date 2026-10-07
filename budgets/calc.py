"""Money math for one saved month.

Amounts are rounded to öre (half up) before they are summed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from .constants import CATEGORIES, MANUAL, MORTGAGE_AMORTIZATION, MORTGAGE_INTEREST

ORE = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value) -> Decimal:
    if value is None or value == "":
        return ZERO
    return Decimal(value).quantize(ORE, rounding=ROUND_HALF_UP)


def monthly_from_annual(balance, annual_rate) -> Decimal:
    return money(Decimal(balance or 0) * Decimal(annual_rate or 0) / Decimal(12))


@dataclass(frozen=True)
class DerivedLine:
    source: str
    name: str
    category: str
    person: str
    amount: Decimal
    note: str


@dataclass(frozen=True)
class MortgageCalc:
    interest: Decimal
    amortization: Decimal
    total: Decimal


def ore(value) -> int:
    """Whole öre. money() has already rounded half away from zero."""
    return int(money(value) * 100)


def rate_micro(value) -> int:
    """Annual rate as millionths. 3% is 30_000, so one step is 0,0001 procentenheter."""
    return int((Decimal(value or 0) * Decimal(1_000_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def div_round_half_away(numerator: int, denominator: int) -> int:
    """Integer division matching Decimal ROUND_HALF_UP, away from zero on a tie."""
    n, d = int(numerator), int(denominator)
    if d < 0:
        n, d = -n, -d
    negative = n < 0
    if negative:
        n = -n
    rounded = (n + d // 2) // d
    return -rounded if negative else rounded


def scale_ore(amount_ore: int, percent: int) -> int:
    return div_round_half_away(int(amount_ore) * int(percent), 100)


def rate_from_micro(micro: int) -> Decimal:
    bounded = max(0, min(int(micro), 1_000_000))
    return (Decimal(bounded) / Decimal(1_000_000)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def scenario_baseline(plan, incomes, expenses) -> dict:
    """Saved rows the what-if sheet scales. Mortgage lines are left out; the sheet recalculates them."""
    income_amounts: dict[str, Decimal] = {}
    income_order: list[str] = []
    for row in incomes:
        if not getattr(row, "active", True):
            continue
        net = money(getattr(row, "net", None))
        if not (getattr(row, "kind", "") or "").strip() and net == ZERO:
            continue
        person = row.person or ""
        if person not in income_amounts:
            income_order.append(person)
            income_amounts[person] = ZERO
        income_amounts[person] += net

    expense_amounts: dict[str, Decimal] = {}
    extra: list[str] = []
    for row in expenses:
        if getattr(row, "source", MANUAL) != MANUAL:
            continue
        if not getattr(row, "active", True):
            continue
        amount = money(getattr(row, "amount", None))
        if not (getattr(row, "name", "") or "").strip() and amount == ZERO:
            continue
        category = (row.category or "").strip()
        if category not in expense_amounts:
            expense_amounts[category] = ZERO
            if category not in CATEGORIES:
                extra.append(category)
        expense_amounts[category] += amount

    return {
        "balanceOre": ore(plan.mortgage_balance),
        "rateMicro": rate_micro(plan.mortgage_rate),
        "amortMicro": rate_micro(plan.amortization_rate),
        "incomes": [
            {"person": name, "ore": ore(income_amounts[name])}
            for name in income_order
            if income_amounts[name] != ZERO
        ],
        "expenses": [
            {"category": name, "ore": ore(expense_amounts[name])}
            for name in list(CATEGORIES) + extra
            if name in expense_amounts and expense_amounts[name] != ZERO
        ],
        "categoryOrder": list(CATEGORIES),
    }


def mortgage_calculation(plan) -> MortgageCalc:
    """Monthly interest and amortization from the balance."""
    interest = monthly_from_annual(plan.mortgage_balance, plan.mortgage_rate)
    amortization = monthly_from_annual(plan.mortgage_balance, plan.amortization_rate)
    return MortgageCalc(interest, amortization, interest + amortization)


def _nonzero(source, name, category, person, amount, note) -> DerivedLine | None:
    if amount == ZERO:
        return None
    return DerivedLine(source, name, category, person, amount, note)


def derived_lines(plan) -> list[DerivedLine]:
    """Saved cost rows produced by the mortgage calculation."""
    mortgage = mortgage_calculation(plan)
    lines = [
        _nonzero(
            MORTGAGE_INTEREST,
            "Bolån, ränta",
            "Boende",
            "",
            mortgage.interest,
            "Från bolånet",
        ),
        _nonzero(
            MORTGAGE_AMORTIZATION,
            "Bolån, amortering",
            "Boende",
            "",
            mortgage.amortization,
            "Från bolånet",
        ),
    ]
    return [line for line in lines if line is not None]


@dataclass
class MoneyLine:
    label: str
    person: str
    category: str
    amount: Decimal
    share: Decimal
    note: str = ""


@dataclass
class PersonRollup:
    person: str
    net: Decimal
    own_costs: Decimal
    difference: Decimal


@dataclass
class CategoryRollup:
    category: str
    amount: Decimal
    share: Decimal

    @property
    def bar_pct(self) -> int:
        return int((self.share * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class Summary:
    incomes: list[MoneyLine]
    expenses: list[MoneyLine]
    income_total: Decimal
    expense_total: Decimal
    left: Decimal
    savings_rate: Decimal | None
    categories: list[CategoryRollup]
    people: list[PersonRollup]
    mortgage: MortgageCalc


def _share(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return ZERO
    return part / whole


def _active_amount(row) -> Decimal | None:
    if not getattr(row, "active", True):
        return None
    return money(getattr(row, "amount", None) if hasattr(row, "amount") else getattr(row, "net", None))


def summarize(plan, incomes, expenses) -> Summary:
    income_lines = []
    for row in incomes:
        if not row.active:
            continue
        net = money(row.net)
        if not (row.kind or "").strip() and net == ZERO:
            continue
        income_lines.append((row, net))
    income_total = sum((net for _, net in income_lines), ZERO)

    expense_rows = []
    for row in expenses:
        if not row.active:
            continue
        amount = money(row.amount)
        if not (row.name or "").strip() and amount == ZERO:
            continue
        expense_rows.append((row, amount))
    expense_total = sum((amount for _, amount in expense_rows), ZERO)
    left = income_total - expense_total
    savings_rate = None if income_total == ZERO else left / income_total

    income_view = [
        MoneyLine(
            label=row.kind,
            person=row.person,
            category="",
            amount=net,
            share=_share(net, income_total),
        )
        for row, net in income_lines
    ]
    expense_view = [
        MoneyLine(
            label=row.name,
            person=row.person,
            category=row.category,
            amount=amount,
            share=_share(amount, expense_total),
            note=row.note or "",
        )
        for row, amount in expense_rows
    ]

    by_category: dict[str, Decimal] = {}
    for row, amount in expense_rows:
        name = (row.category or "").strip()
        if not name:
            continue
        by_category[name] = by_category.get(name, ZERO) + amount
    categories = []
    seen = set()
    for name in list(CATEGORIES) + sorted(by_category):
        if name in seen or name not in by_category:
            continue
        seen.add(name)
        amount = by_category[name]
        categories.append(CategoryRollup(name, amount, _share(amount, expense_total)))

    mortgage = mortgage_calculation(plan)

    ordered = []
    for row, _amount in (*income_lines, *expense_rows):
        if row.person and row.person not in ordered:
            ordered.append(row.person)
    people = []
    for name in ordered:
        net = sum((net for row, net in income_lines if row.person == name), ZERO)
        own = sum((amount for row, amount in expense_rows if row.person == name), ZERO)
        people.append(PersonRollup(name, net, own, net - own))

    return Summary(
        incomes=income_view,
        expenses=expense_view,
        income_total=income_total,
        expense_total=expense_total,
        left=left,
        savings_rate=savings_rate,
        categories=categories,
        people=people,
        mortgage=mortgage,
    )
