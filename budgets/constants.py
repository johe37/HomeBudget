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

MANUAL = "manual"
MORTGAGE_INTEREST = "mortgage_interest"
MORTGAGE_AMORTIZATION = "mortgage_amortization"

DERIVED_SOURCES = [
    MORTGAGE_INTEREST,
    MORTGAGE_AMORTIZATION,
]

SOURCE_CHOICES = [
    (MANUAL, "Manuell"),
    (MORTGAGE_INTEREST, "Bolån, ränta"),
    (MORTGAGE_AMORTIZATION, "Bolån, amortering"),
]
