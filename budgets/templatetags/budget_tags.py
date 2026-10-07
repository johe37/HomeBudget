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
