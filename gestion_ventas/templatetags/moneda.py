from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template


register = template.Library()


@register.filter
def cop(value):
    if value in (None, ""):
        return "$ 0"

    try:
        amount = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return value

    sign = "-$ " if amount < 0 else "$ "
    absolute = abs(int(amount))
    return f"{sign}{absolute:,}".replace(",", ".")
