SWEDISH_MONTHS = [
    None,
    "Januari",
    "Februari",
    "Mars",
    "April",
    "Maj",
    "Juni",
    "Juli",
    "Augusti",
    "September",
    "Oktober",
    "November",
    "December",
]

CATEGORIES = ["Boende", "Transport", "Leva", "Lån", "Sparande", "Övrigt"]
INCOME_KINDS = [
    "Lön",
    "Barnbidrag",
    "Föräldrapenning",
    "Bostadsbidrag",
    "Kapital",
    "Utbetalning",
    "Övrig inkomst",
]
EXTRA_PEOPLE = ["Barn", "Annan"]

MANUAL = "manual"
MORTGAGE_INTEREST = "mortgage_interest"
MORTGAGE_AMORTIZATION = "mortgage_amortization"
PRIMARY_LOAN = "primary_loan"
PRIMARY_INSURANCE = "primary_insurance"
PRIMARY_FUEL = "primary_fuel"
PARTNER_LOAN = "partner_loan"
PARTNER_INSURANCE = "partner_insurance"
PARTNER_FUEL = "partner_fuel"

DERIVED_SOURCES = [
    MORTGAGE_INTEREST,
    MORTGAGE_AMORTIZATION,
    PRIMARY_LOAN,
    PRIMARY_INSURANCE,
    PRIMARY_FUEL,
    PARTNER_LOAN,
    PARTNER_INSURANCE,
    PARTNER_FUEL,
]

SOURCE_CHOICES = [
    (MANUAL, "Manuell"),
    (MORTGAGE_INTEREST, "Bolån, ränta"),
    (MORTGAGE_AMORTIZATION, "Bolån, amortering"),
    (PRIMARY_LOAN, "Billån, person 1"),
    (PRIMARY_INSURANCE, "Bilförsäkring, person 1"),
    (PRIMARY_FUEL, "Drivmedel, person 1"),
    (PARTNER_LOAN, "Billån, person 2"),
    (PARTNER_INSURANCE, "Bilförsäkring, person 2"),
    (PARTNER_FUEL, "Drivmedel, person 2"),
]
