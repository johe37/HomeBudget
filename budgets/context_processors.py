from .constants import CATEGORIES, EXTRA_PEOPLE, INCOME_KINDS


def household(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    from .services import household_for

    home = household_for(request.user)
    people = []
    for name in (home.shared_name, home.primary_name, home.partner_name, *EXTRA_PEOPLE):
        if name and name not in people:
            people.append(name)
    return {
        "household": home,
        "person_suggestions": people,
        "category_suggestions": CATEGORIES,
        "income_kind_suggestions": INCOME_KINDS,
    }
