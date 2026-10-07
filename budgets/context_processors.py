from .constants import CATEGORIES, INCOME_KINDS


def budget_choices(request):
    return {
        "category_suggestions": CATEGORIES,
        "income_kind_suggestions": INCOME_KINDS,
    }
