from .constants import CATEGORIES, EXTRA_PEOPLE, INCOME_KINDS


def budget_choices(request):
    return {
        "person_suggestions": list(EXTRA_PEOPLE),
        "category_suggestions": CATEGORIES,
        "income_kind_suggestions": INCOME_KINDS,
    }
