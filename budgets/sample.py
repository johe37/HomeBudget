"""Invented Swedish household figures for trying a monthly budget.

The amounts sit in ordinary ranges and then move a little at random.
They are not a recommendation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from .constants import CATEGORIES

ORE = Decimal("0.01")
BARNBIDRAG = Decimal("1250.00")
_NAMES = ("Anna", "Erik", "Sara", "Johan", "Linnea", "Oscar", "Maja", "Noah", "Elin", "Viktor")


@dataclass(frozen=True)
class SampleIncome:
    kind: str
    person: str
    gross: Decimal | None
    tax_rate: Decimal | None
    net: Decimal


@dataclass(frozen=True)
class SampleExpense:
    name: str
    category: str
    person: str
    amount: Decimal
    note: str


@dataclass(frozen=True)
class SampleDraft:
    label: str
    note: str
    mortgage_balance: Decimal
    mortgage_rate: Decimal
    amortization_rate: Decimal
    incomes: tuple[SampleIncome, ...]
    expenses: tuple[SampleExpense, ...]


def build_sample(rng: random.Random | None = None) -> SampleDraft:
    """One household. The same rng seed returns the same draft."""
    picker = rng if rng is not None else random.Random()
    recipe = picker.choice((_ensam_hyra, _par_hyra, _par_bostadsratt, _familj_villa))
    draft = recipe(picker)
    _check_draft(draft)
    return draft


def _pick_amount(rng: random.Random, low: int, high: int, step: int = 50) -> Decimal:
    low, high, step = int(low), int(high), int(step)
    if step <= 0 or low > high:
        raise ValueError("amount range")
    stops = (high - low) // step
    return Decimal(low + rng.randint(0, stops) * step)


def _names(rng: random.Random, count: int) -> tuple[str, ...]:
    return tuple(rng.sample(_NAMES, count))


def _salary(rng: random.Random, person: str, low: int, high: int) -> SampleIncome:
    gross = _pick_amount(rng, low, high, 500)
    # 29.0%–33.5% municipal tax, stored as a share.
    tax_rate = (Decimal(rng.randint(290, 335)) / Decimal(1000)).quantize(Decimal("0.000001"))
    net = (gross * (Decimal(1) - tax_rate)).quantize(ORE, rounding=ROUND_HALF_UP)
    return SampleIncome("Lön", person, gross, tax_rate, net)


def _cost(
    rng: random.Random,
    name: str,
    category: str,
    low: int,
    high: int,
    step: int = 50,
    person: str = "",
    note: str = "",
) -> SampleExpense:
    return SampleExpense(name, category, person, _pick_amount(rng, low, high, step), note)


def _maybe(rng: random.Random, chance: float, row: SampleExpense) -> list[SampleExpense]:
    if rng.random() < chance:
        return [row]
    return []


def _housing_bills(rng: random.Random, el: tuple[int, int]) -> list[SampleExpense]:
    return [
        _cost(rng, "El", "Boende", el[0], el[1], 50),
        _cost(rng, "Hemförsäkring", "Boende", 120, 320, 10),
        _cost(rng, "Bredband", "Boende", 290, 490, 10),
    ]


def _living(rng: random.Random, people: int, adults: int) -> list[SampleExpense]:
    mat_low = 2800 + 1500 * (people - 1)
    mat_high = 4200 + 2000 * (people - 1)
    rows = [
        _cost(rng, "Mat", "Leva", mat_low, mat_high, 100),
        _cost(rng, "Mobil", "Leva", 150 * adults, 350 * adults, 10),
    ]
    rows += _maybe(rng, 0.8, _cost(rng, "Streamingtjänster", "Leva", 100, 350, 10))
    rows += _maybe(rng, 0.55, _cost(rng, "Kläder", "Leva", 300, 1200, 50))
    rows += _maybe(rng, 0.35, _cost(rng, "Apotek", "Leva", 80, 350, 10))
    return rows


def _transport(rng: random.Random, adults: int, car_chance: float) -> list[SampleExpense]:
    car = rng.random() < car_chance
    transit = (not car) or rng.random() < 0.4
    rows = []
    if transit:
        per_adult = _pick_amount(rng, 650, 1100, 50)
        rows.append(SampleExpense("Kollektivtrafik", "Transport", "", per_adult * adults, ""))
    if car:
        rows.append(_cost(rng, "Drivmedel", "Transport", 800, 2400, 50))
        rows.append(_cost(rng, "Bilförsäkring", "Transport", 350, 900, 50))
    return rows


def _extras(rng: random.Random, adults: tuple[str, ...]) -> list[SampleExpense]:
    rows = []
    rows += _maybe(rng, 0.72, _cost(rng, "Månadssparande", "Sparande", 500, 3000, 100))
    if rng.random() < 0.3:
        person = adults[0] if len(adults) == 1 else rng.choice(adults)
        rows.append(_cost(rng, "Studielån", "Lån", 300, 1300, 50, person=person, note="CSN"))
    rows += _maybe(rng, 0.4, _cost(rng, "Fritid", "Övrigt", 200, 900, 50))
    return rows


def _mortgage(rng: random.Random, low: int, high: int) -> tuple[Decimal, Decimal, Decimal]:
    balance = _pick_amount(rng, low, high, 100_000)
    # 2.40%–4.20% in steps of 0.05, stored as a share.
    rate = (Decimal("2.40") + Decimal("0.05") * rng.randint(0, 36)) / Decimal(100)
    rate = rate.quantize(Decimal("0.000001"))
    amort = Decimal("0.020000") if rng.random() < 0.65 else Decimal("0.010000")
    return balance, rate, amort


def _no_mortgage() -> tuple[Decimal, Decimal, Decimal]:
    return Decimal("0.00"), Decimal("0.000000"), Decimal("0.000000")


def _draft(
    label: str,
    adults: tuple[str, ...],
    child: bool,
    mortgage: tuple[Decimal, Decimal, Decimal],
    expenses: list[SampleExpense],
    rng: random.Random,
) -> SampleDraft:
    incomes = [
        _salary(rng, person, 32000 if index == 0 else 24000, 52000 if index == 0 else 46000)
        for index, person in enumerate(adults)
    ]
    if child:
        incomes.append(SampleIncome("Barnbidrag", "", None, None, BARNBIDRAG))
    who = label[0].upper() + label[1:]
    note = f"Slumpad exempelbudget. {who}."
    balance, rate, amort = mortgage
    return SampleDraft(
        label=label,
        note=note,
        mortgage_balance=balance,
        mortgage_rate=rate,
        amortization_rate=amort,
        incomes=tuple(incomes),
        expenses=tuple(expenses),
    )


def _ensam_hyra(rng: random.Random) -> SampleDraft:
    adults = _names(rng, 1)
    expenses = [_cost(rng, "Hyra", "Boende", 7500, 11500, 100)]
    expenses += _housing_bills(rng, (400, 1200))
    expenses += _living(rng, people=1, adults=1)
    expenses += _transport(rng, 1, car_chance=0.25)
    expenses += _extras(rng, adults)
    return _draft("en vuxen i hyresrätt", adults, False, _no_mortgage(), expenses, rng)


def _par_hyra(rng: random.Random) -> SampleDraft:
    adults = _names(rng, 2)
    expenses = [_cost(rng, "Hyra", "Boende", 10000, 15500, 100)]
    expenses += _housing_bills(rng, (500, 1500))
    expenses += _living(rng, people=2, adults=2)
    expenses += _transport(rng, 2, car_chance=0.45)
    expenses += _extras(rng, adults)
    return _draft("två vuxna i hyresrätt", adults, False, _no_mortgage(), expenses, rng)


def _par_bostadsratt(rng: random.Random) -> SampleDraft:
    adults = _names(rng, 2)
    expenses = [_cost(rng, "Avgift", "Boende", 3500, 7200, 100)]
    expenses += _housing_bills(rng, (500, 1600))
    expenses += _living(rng, people=2, adults=2)
    expenses += _transport(rng, 2, car_chance=0.55)
    expenses += _extras(rng, adults)
    return _draft(
        "två vuxna i bostadsrätt",
        adults,
        False,
        _mortgage(rng, 1_500_000, 3_200_000),
        expenses,
        rng,
    )


def _familj_villa(rng: random.Random) -> SampleDraft:
    adults = _names(rng, 2)
    expenses = [
        _cost(
            rng,
            "Driftskostnad",
            "Boende",
            2500,
            5500,
            100,
            note="Vatten, sophämtning och underhåll",
        )
    ]
    expenses += _housing_bills(rng, (1400, 3200))
    expenses += _living(rng, people=3, adults=2)
    expenses += _transport(rng, 2, car_chance=0.85)
    expenses += _extras(rng, adults)
    return _draft(
        "två vuxna och ett barn i villa",
        adults,
        True,
        _mortgage(rng, 2_200_000, 4_500_000),
        expenses,
        rng,
    )


def _check_draft(draft: SampleDraft) -> None:
    if not any(row.kind == "Lön" for row in draft.incomes):
        raise ValueError("sample is missing a salary")
    categories = {row.category for row in draft.expenses}
    if not categories <= set(CATEGORIES):
        raise ValueError("sample uses an unknown category")
    if "Boende" not in categories or "Leva" not in categories or "Transport" not in categories:
        raise ValueError("sample is missing an ordinary cost")
    if not any(row.name == "Mat" for row in draft.expenses):
        raise ValueError("sample is missing food")
