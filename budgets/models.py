from django.conf import settings
from django.db import models
from django.db.models import Q

from .constants import (
    DERIVED_SOURCES,
    MANUAL,
    SOURCE_CHOICES,
    SWEDISH_MONTHS,
)


class Plan(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="plans",
    )
    year = models.PositiveSmallIntegerField("år")
    month = models.PositiveSmallIntegerField("månad")
    note = models.CharField("anteckning", max_length=240, blank=True)
    mortgage_balance = models.DecimalField("bolåneskuld", max_digits=12, decimal_places=2, default=0)
    mortgage_rate = models.DecimalField("ränta", max_digits=7, decimal_places=6, default=0)
    amortization_rate = models.DecimalField("amortering", max_digits=7, decimal_places=6, default=0)
    primary_loan = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    primary_insurance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    primary_fuel = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    partner_loan = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    partner_insurance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    partner_fuel = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(fields=["user", "year", "month"], name="unique_plan_month"),
        ]

    def __str__(self):
        return self.title

    @property
    def title(self) -> str:
        return f"{SWEDISH_MONTHS[self.month]} {self.year}"


class Income(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="incomes")
    kind = models.CharField("typ", max_length=80, blank=True)
    person = models.CharField("person", max_length=80, blank=True)
    gross = models.DecimalField("brutto", max_digits=12, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField("skatt", max_digits=7, decimal_places=6, null=True, blank=True)
    net = models.DecimalField("netto", max_digits=12, decimal_places=2, default=0)
    active = models.BooleanField("aktiv", default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.kind} {self.person}"


class Expense(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="expenses")
    name = models.CharField("post", max_length=120, blank=True)
    category = models.CharField("kategori", max_length=80, blank=True)
    person = models.CharField("vem", max_length=80, blank=True)
    amount = models.DecimalField("belopp", max_digits=12, decimal_places=2, default=0)
    note = models.CharField("anteckning", max_length=160, blank=True)
    active = models.BooleanField("aktiv", default=True)
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default=MANUAL)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "source"],
                condition=~Q(source=MANUAL),
                name="unique_derived_expense",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_derived(self) -> bool:
        return self.source in DERIVED_SOURCES
