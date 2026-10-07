"""Csv export and import for one or more named budgets.

The file is UTF-8, separated by semicolons, with a decimal comma. A budget can
hold a budget row, income rows and manual cost rows. Mortgage interest and
amortization are left out and calculated again on import.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction

from .constants import MANUAL
from .models import Expense, Income, Plan
from .services import name_taken, sync_derived

COLUMNS = [
    "budget",
    "rad",
    "anteckning",
    "bolåneskuld",
    "ränta_procent",
    "amortering_procent",
    "typ",
    "person",
    "brutto",
    "skatt_procent",
    "netto",
    "post",
    "kategori",
    "belopp",
    "aktiv",
]

ROW_BUDGET = "budget"
ROW_INCOME = "inkomst"
ROW_COST = "kostnad"
_ROW_KINDS = {ROW_BUDGET, ROW_INCOME, ROW_COST}
_FORMULA_PREFIX = ("=", "+", "-", "@")
_RATE = Decimal("0.000001")


class BudgetCsvError(Exception):
    """The file cannot be imported as monthly budgets."""


@dataclass
class _IncomeRow:
    kind: str
    person: str
    gross: Decimal | None
    tax_rate: Decimal | None
    net: Decimal
    active: bool


@dataclass
class _ExpenseRow:
    name: str
    category: str
    person: str
    amount: Decimal
    note: str
    active: bool


@dataclass
class _Draft:
    name: str
    note: str = ""
    balance: Decimal = Decimal("0.00")
    mortgage_rate: Decimal = Decimal("0")
    amortization_rate: Decimal = Decimal("0")
    has_budget_row: bool = False
    incomes: list[_IncomeRow] = field(default_factory=list)
    expenses: list[_ExpenseRow] = field(default_factory=list)


def export_plans(plans) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=COLUMNS,
        delimiter=";",
        lineterminator="\r\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    for plan in plans:
        writer.writerow(
            {
                "budget": _csv_text(plan.name),
                "rad": ROW_BUDGET,
                "anteckning": _csv_text(plan.note),
                "bolåneskuld": _format_decimal(plan.mortgage_balance, 2),
                "ränta_procent": _format_decimal(Decimal(plan.mortgage_rate) * 100, 4),
                "amortering_procent": _format_decimal(Decimal(plan.amortization_rate) * 100, 4),
            }
        )
        for income in plan.incomes.all():
            writer.writerow(
                {
                    "budget": _csv_text(plan.name),
                    "rad": ROW_INCOME,
                    "typ": _csv_text(income.kind),
                    "person": _csv_text(income.person),
                    "brutto": _format_decimal(income.gross, 2),
                    "skatt_procent": _format_decimal(
                        None if income.tax_rate is None else Decimal(income.tax_rate) * 100,
                        4,
                    ),
                    "netto": _format_decimal(income.net, 2),
                    "aktiv": "1" if income.active else "0",
                }
            )
        for expense in plan.expenses.filter(source=MANUAL):
            writer.writerow(
                {
                    "budget": _csv_text(plan.name),
                    "rad": ROW_COST,
                    "anteckning": _csv_text(expense.note),
                    "person": _csv_text(expense.person),
                    "post": _csv_text(expense.name),
                    "kategori": _csv_text(expense.category),
                    "belopp": _format_decimal(expense.amount, 2),
                    "aktiv": "1" if expense.active else "0",
                }
            )
    return buffer.getvalue().encode("utf-8-sig")


def import_plans(user, raw: bytes) -> list[Plan]:
    drafts = _parse(raw)
    if not drafts:
        raise BudgetCsvError("Filen innehåller ingen månadsbudget.")
    for draft in drafts:
        if name_taken(user, draft.name):
            raise BudgetCsvError(f"Det namnet finns redan: {draft.name}.")
    created = []
    with transaction.atomic():
        for draft in drafts:
            plan = Plan.objects.create(
                user=user,
                name=draft.name,
                note=draft.note,
                mortgage_balance=draft.balance,
                mortgage_rate=draft.mortgage_rate,
                amortization_rate=draft.amortization_rate,
            )
            Income.objects.bulk_create(
                [
                    Income(
                        plan=plan,
                        kind=row.kind,
                        person=row.person,
                        gross=row.gross,
                        tax_rate=row.tax_rate,
                        net=row.net,
                        active=row.active,
                        sort_order=index,
                    )
                    for index, row in enumerate(draft.incomes)
                ]
            )
            Expense.objects.bulk_create(
                [
                    Expense(
                        plan=plan,
                        name=row.name,
                        category=row.category,
                        person=row.person,
                        amount=row.amount,
                        note=row.note,
                        active=row.active,
                        source=MANUAL,
                        sort_order=100 + index,
                    )
                    for index, row in enumerate(draft.expenses)
                ]
            )
            sync_derived(plan)
            created.append(plan)
    return created


def _parse(raw: bytes) -> list[_Draft]:
    if len(raw) > 2_000_000:
        raise BudgetCsvError("Filen är för stor.")
    text = _decode(raw)
    if not text.strip():
        raise BudgetCsvError("Filen är tom.")
    first_line = text.splitlines()[0]
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = {(name or "").strip().casefold() for name in reader.fieldnames or []}
    if not {"budget", "rad"} <= headers:
        raise BudgetCsvError("Filen behöver kolumnerna budget och rad.")

    drafts: dict[str, _Draft] = {}
    order: list[str] = []
    for raw_row in reader:
        line_no = reader.line_num
        row = {
            (key or "").strip().casefold(): (value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        if not any(row.values()):
            continue
        kind = row.get("rad", "").casefold()
        if kind not in _ROW_KINDS:
            raise BudgetCsvError(f"Rad {line_no}: raden ska vara budget, inkomst eller kostnad.")
        name = _uncsv_text(row.get("budget", ""))
        if not name:
            raise BudgetCsvError(f"Rad {line_no}: skriv namnet på månadsbudgeten.")
        if len(name) > 80:
            raise BudgetCsvError(f"Rad {line_no}: namnet får vara högst 80 tecken.")
        key = name.casefold()
        draft = drafts.get(key)
        if draft is None:
            draft = _Draft(name=name)
            drafts[key] = draft
            order.append(key)
        try:
            if kind == ROW_BUDGET:
                _read_budget(draft, row, line_no)
            elif kind == ROW_INCOME:
                _read_income(draft, row, line_no)
            else:
                _read_cost(draft, row, line_no)
        except BudgetCsvError:
            raise
        except (InvalidOperation, ArithmeticError) as exc:
            raise BudgetCsvError(f"Rad {line_no}: ett belopp går inte att läsa.") from exc
    return [drafts[key] for key in order]


def _read_budget(draft: _Draft, row: dict[str, str], line_no: int) -> None:
    if draft.has_budget_row:
        raise BudgetCsvError(f"Rad {line_no}: {draft.name} har redan en budgetrad.")
    note = _limited(_uncsv_text(row.get("anteckning", "")), 240, line_no, "anteckningen")
    draft.note = note
    draft.balance = _money(row.get("bolåneskuld", ""), line_no, "bolåneskulden") or Decimal("0.00")
    if draft.balance < 0:
        raise BudgetCsvError(f"Rad {line_no}: bolåneskulden kan inte vara negativ.")
    draft.mortgage_rate = _percent_rate(row.get("ränta_procent", ""), line_no, "räntan")
    draft.amortization_rate = _percent_rate(
        row.get("amortering_procent", ""),
        line_no,
        "amorteringen",
    )
    draft.has_budget_row = True


def _read_income(draft: _Draft, row: dict[str, str], line_no: int) -> None:
    kind = _limited(_uncsv_text(row.get("typ", "")), 80, line_no, "typen")
    person = _limited(_uncsv_text(row.get("person", "")), 80, line_no, "personen")
    gross = _money(row.get("brutto", ""), line_no, "brutto")
    tax = _optional_percent(row.get("skatt_procent", ""), line_no, "skatten")
    net = _money(row.get("netto", ""), line_no, "nettot") or Decimal("0.00")
    if not any((kind, person, gross is not None, tax is not None, net != 0)):
        return
    draft.incomes.append(
        _IncomeRow(
            kind=kind,
            person=person,
            gross=gross,
            tax_rate=tax,
            net=net,
            active=_active(row.get("aktiv", ""), line_no),
        )
    )


def _read_cost(draft: _Draft, row: dict[str, str], line_no: int) -> None:
    name = _limited(_uncsv_text(row.get("post", "")), 120, line_no, "posten")
    category = _limited(_uncsv_text(row.get("kategori", "")), 80, line_no, "kategorin")
    person = _limited(_uncsv_text(row.get("person", "")), 80, line_no, "personen")
    note = _limited(_uncsv_text(row.get("anteckning", "")), 160, line_no, "anteckningen")
    amount = _money(row.get("belopp", ""), line_no, "beloppet") or Decimal("0.00")
    if not any((name, category, person, note, amount != 0)):
        return
    draft.expenses.append(
        _ExpenseRow(
            name=name,
            category=category,
            person=person,
            amount=amount,
            note=note,
            active=_active(row.get("aktiv", ""), line_no),
        )
    )


def _decode(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def _format_decimal(value, places: int) -> str:
    if value is None:
        return ""
    quantum = Decimal("1").scaleb(-places)
    text = f"{Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP):.{places}f}"
    text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _parse_decimal(text: str, places: int, line_no: int, label: str) -> Decimal | None:
    cleaned = (
        (text or "")
        .replace("\u00a0", "")
        .replace(" ", "")
        .replace("kr", "")
        .replace("%", "")
        .strip()
    )
    if cleaned == "":
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation as exc:
        raise BudgetCsvError(f"Rad {line_no}: {label} går inte att läsa.") from exc
    quantum = Decimal("1").scaleb(-places)
    return parsed.quantize(quantum, rounding=ROUND_HALF_UP)


def _money(text: str, line_no: int, label: str) -> Decimal | None:
    return _parse_decimal(text, 2, line_no, label)


def _percent_rate(text: str, line_no: int, label: str) -> Decimal:
    parsed = _optional_percent(text, line_no, label)
    return Decimal("0") if parsed is None else parsed


def _optional_percent(text: str, line_no: int, label: str) -> Decimal | None:
    parsed = _parse_decimal(text, 4, line_no, label)
    if parsed is None:
        return None
    if parsed < 0 or parsed > 100:
        raise BudgetCsvError(f"Rad {line_no}: {label} ska vara mellan 0 och 100 procent.")
    return (parsed / Decimal(100)).quantize(_RATE, rounding=ROUND_HALF_UP)


def _active(text: str, line_no: int) -> bool:
    value = (text or "").strip().casefold()
    if value in ("", "1", "ja", "true", "sant", "aktiv"):
        return True
    if value in ("0", "nej", "false", "falskt", "inaktiv"):
        return False
    raise BudgetCsvError(f"Rad {line_no}: aktiv ska vara 1 eller 0.")


def _limited(text: str, limit: int, line_no: int, label: str) -> str:
    if len(text) > limit:
        raise BudgetCsvError(f"Rad {line_no}: {label} är för lång.")
    return text


def _csv_text(value: str) -> str:
    text = value or ""
    if text[:1] in _FORMULA_PREFIX:
        return "'" + text
    return text


def _uncsv_text(value: str) -> str:
    text = (value or "").strip()
    if len(text) > 1 and text[0] == "'" and text[1] in _FORMULA_PREFIX:
        return text[1:]
    return text
