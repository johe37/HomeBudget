from decimal import Decimal, ROUND_HALF_UP

from django import template

register = template.Library()


def _decimal(value) -> Decimal:
    return Decimal(value)


@register.filter
def kr(value):
    if value is None or value == "":
        return "–"
    amount = _decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    whole, frac = f"{amount:.2f}".split(".")
    parts = []
    while whole:
        parts.append(whole[-3:])
        whole = whole[:-3]
    body = " ".join(reversed(parts))
    if frac == "00":
        return f"{sign}{body} kr"
    return f"{sign}{body},{frac} kr"


@register.filter
def pct(value):
    """Format a fraction (0.362) as Swedish percent with one decimal."""
    if value is None or value == "":
        return "–"
    number = (_decimal(value) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{number:.1f}".replace(".", ",") + " %"


def _rate_number(value) -> Decimal:
    return (_decimal(value) * 100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _rate_text(number: Decimal) -> str:
    text = f"{abs(number):.4f}".rstrip("0").rstrip(".")
    if text == "":
        text = "0"
    return text.replace(".", ",")


@register.filter
def rate(value):
    """Format an annual rate (0.035525) as percent, keeping up to four decimals."""
    if value is None or value == "":
        return "–"
    number = _rate_number(value)
    sign = "-" if number < 0 else ""
    return f"{sign}{_rate_text(number)} %"


@register.filter
def points(value):
    """Format a difference of annual rates as percentage points."""
    if value is None or value == "":
        return "–"
    number = _rate_number(value)
    if number == 0:
        return "0 procentenheter"
    sign = "+" if number > 0 else "-"
    unit = "procentenhet" if abs(number) == 1 else "procentenheter"
    return f"{sign}{_rate_text(number)} {unit}"


@register.filter
def abs_kr(value):
    if value is None or value == "":
        return "–"
    return kr(abs(_decimal(value)))


@register.filter
def delta_kr(value):
    if value is None or value == "":
        return "–"
    text = kr(value)
    if _decimal(value) > 0:
        return f"+{text}"
    return text
