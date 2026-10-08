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


@dataclass(frozen=True)
class FieldGap:
    label: str
    left: Decimal
    right: Decimal
    unit: str

    @property
    def delta(self) -> Decimal:
        return self.right - self.left

    @property
    def changed(self) -> bool:
        return self.left != self.right


@dataclass(frozen=True)
class RowGap:
    label: str
    meta: str
    left: Decimal | None
    right: Decimal | None
    group: str = ""
    category: str = ""
    person: str = ""
    move: bool = False

    @property
    def delta(self) -> Decimal | None:
        if self.left is None or self.right is None:
            return None
        return self.right - self.left

    @property
    def shown_delta(self) -> Decimal:
        """Mot minus från. A missing side counts as zero."""
        return (self.right if self.right is not None else ZERO) - (
            self.left if self.left is not None else ZERO
        )

    @property
    def side(self) -> str:
        if self.move:
            return "flytt"
        if self.left is None:
            return "ny"
        if self.right is None:
            return "borta"
        return ""


@dataclass(frozen=True)
class PlanDiff:
    left_summary: Summary
    right_summary: Summary
    mortgage: list[FieldGap]
    incomes: list[RowGap]
    expenses: list[RowGap]
    income_same: int
    expense_same: int

    @property
    def left_delta(self) -> Decimal:
        return self.right_summary.left - self.left_summary.left

    @property
    def income_delta(self) -> Decimal:
        return self.right_summary.income_total - self.left_summary.income_total

    @property
    def expense_delta(self) -> Decimal:
        return self.right_summary.expense_total - self.left_summary.expense_total

    @property
    def income_note(self) -> str:
        return _quiet_note(self.incomes, self.income_same, "inkomst", "inkomster")

    @property
    def expense_note(self) -> str:
        return _quiet_note(self.expenses, self.expense_same, "kostnad", "kostnader")

    @property
    def kvar_word(self) -> str:
        if self.left_delta > 0:
            return "mer"
        if self.left_delta < 0:
            return "mindre"
        return ""

    @property
    def unchanged_note(self) -> str:
        parts = []
        if self.mortgage_same:
            parts.append("Bolånet är lika.")
        if not self.incomes and self.income_same:
            parts.append(self.income_note)
        if not self.expenses and self.expense_same:
            parts.append(self.expense_note)
        return " ".join(parts)

    @property
    def same(self) -> bool:
        return not self.left_delta and not self.incomes and not self.expenses and not any(
            row.changed for row in self.mortgage
        )

    @property
    def mortgage_same(self) -> bool:
        return not any(row.changed for row in self.mortgage)


def _quiet_note(gaps: list[RowGap], same: int, noun: str, plural: str) -> str:
    if gaps and same == 1:
        return f"1 {noun} är lika och visas inte."
    if gaps and same:
        return f"{same} {plural} är lika och visas inte."
    if not gaps and same:
        return f"{plural[:1].upper()}{plural[1:]} är lika."
    if not gaps:
        return f"Inga {plural} att jämföra."
    return ""


def _active_incomes(incomes):
    rows = []
    for row in incomes:
        if not getattr(row, "active", True):
            continue
        net = money(getattr(row, "net", None))
        if not (getattr(row, "kind", "") or "").strip() and net == ZERO:
            continue
        rows.append(row)
    return rows


def _active_manual_expenses(expenses):
    rows = []
    for row in expenses:
        if getattr(row, "source", MANUAL) != MANUAL:
            continue
        if not getattr(row, "active", True):
            continue
        amount = money(getattr(row, "amount", None))
        if not (getattr(row, "name", "") or "").strip() and amount == ZERO:
            continue
        rows.append(row)
    return rows


def _who(person: str) -> str:
    return person or "–"


def _move_meta(gone: RowGap, added: RowGap) -> str:
    shift = f"{_who(gone.person)} → {_who(added.person)}"
    if gone.category:
        return f"{gone.category} · {shift}"
    return shift


def _collapse_moves(gaps: list[RowGap]) -> list[RowGap]:
    """One post that only changed person is a move, not a removal plus an addition."""
    grouped: dict[str, list[int]] = {}
    for index, gap in enumerate(gaps):
        if gap.left is None or gap.right is None:
            grouped.setdefault(gap.group, []).append(index)
    partner: dict[int, int] = {}
    for indexes in grouped.values():
        gone = [index for index in indexes if gaps[index].right is None]
        added = [index for index in indexes if gaps[index].left is None]
        if len(gone) == 1 and len(added) == 1:
            partner[gone[0]] = added[0]
            partner[added[0]] = gone[0]
    folded: list[RowGap] = []
    consumed: set[int] = set()
    for index, gap in enumerate(gaps):
        if index in consumed:
            continue
        other = partner.get(index)
        if other is None:
            folded.append(gap)
            continue
        consumed.add(other)
        gone = gap if gap.right is None else gaps[other]
        added = gaps[other] if gap.right is None else gap
        folded.append(
            RowGap(
                gone.label,
                _move_meta(gone, added),
                gone.left,
                added.right,
                group=gone.group,
                category=gone.category,
                move=True,
            )
        )
    return folded


def _pair(left_rows, right_rows, key, label, meta, amount, group, category, person) -> tuple[list[RowGap], int]:
    left_buckets: dict = {}
    order = []
    for row in left_rows:
        bucket = key(row)
        if bucket not in left_buckets:
            order.append(bucket)
            left_buckets[bucket] = []
        left_buckets[bucket].append(row)
    right_buckets: dict = {}
    for row in right_rows:
        bucket = key(row)
        if bucket not in right_buckets:
            if bucket not in left_buckets:
                order.append(bucket)
            right_buckets[bucket] = []
        right_buckets[bucket].append(row)
    gaps = []
    same = 0
    for bucket in order:
        lefts = left_buckets.get(bucket, [])
        rights = right_buckets.get(bucket, [])
        for index in range(max(len(lefts), len(rights))):
            left = lefts[index] if index < len(lefts) else None
            right = rights[index] if index < len(rights) else None
            left_amount = amount(left) if left is not None else None
            right_amount = amount(right) if right is not None else None
            if left_amount is not None and left_amount == right_amount:
                same += 1
                continue
            source = left if left is not None else right
            gaps.append(
                RowGap(
                    label(source),
                    meta(source),
                    left_amount,
                    right_amount,
                    group=group(source),
                    category=category(source),
                    person=person(source),
                )
            )
    return _collapse_moves(gaps), same


def _income_key(row):
    return (row.person or "", (row.kind or "").strip())


def _income_label(row):
    return (row.kind or "").strip() or "Inkomst"


def _income_meta(row):
    return row.person or ""


def _income_group(row):
    return (row.kind or "").strip() or "Inkomst"


def _income_category(row):
    return ""


def _income_person(row):
    return row.person or ""


def _expense_key(row):
    return ((row.category or "").strip(), (row.name or "").strip(), row.person or "")


def _expense_label(row):
    return (row.name or "").strip() or "Kostnad"


def _expense_meta(row):
    parts = [(row.category or "").strip(), row.person or ""]
    return " · ".join(part for part in parts if part)


def _expense_group(row):
    return f"{(row.category or '').strip()}\0{_expense_label(row)}"


def _expense_category(row):
    return (row.category or "").strip()


def _expense_person(row):
    return row.person or ""


def compare_plans(left, right, left_incomes, left_expenses, right_incomes, right_expenses) -> PlanDiff:
    """What changed from left to right. Mortgage rows are not repeated under costs."""
    left_summary = summarize(left, left_incomes, left_expenses)
    right_summary = summarize(right, right_incomes, right_expenses)
    left_mortgage = mortgage_calculation(left)
    right_mortgage = mortgage_calculation(right)
    incomes, income_same = _pair(
        _active_incomes(left_incomes),
        _active_incomes(right_incomes),
        _income_key,
        _income_label,
        _income_meta,
        lambda row: money(row.net),
        _income_group,
        _income_category,
        _income_person,
    )
    expenses, expense_same = _pair(
        _active_manual_expenses(left_expenses),
        _active_manual_expenses(right_expenses),
        _expense_key,
        _expense_label,
        _expense_meta,
        lambda row: money(row.amount),
        _expense_group,
        _expense_category,
        _expense_person,
    )
    return PlanDiff(
        left_summary=left_summary,
        right_summary=right_summary,
        mortgage=[
            FieldGap("Skuld", money(left.mortgage_balance), money(right.mortgage_balance), "kr"),
            FieldGap("Ränta", Decimal(left.mortgage_rate or 0), Decimal(right.mortgage_rate or 0), "rate"),
            FieldGap(
                "Amortering",
                Decimal(left.amortization_rate or 0),
                Decimal(right.amortization_rate or 0),
                "rate",
            ),
            FieldGap("Ränta per månad", left_mortgage.interest, right_mortgage.interest, "kr"),
            FieldGap("Amortering per månad", left_mortgage.amortization, right_mortgage.amortization, "kr"),
        ],
        incomes=incomes,
        expenses=expenses,
        income_same=income_same,
        expense_same=expense_same,
    )


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
