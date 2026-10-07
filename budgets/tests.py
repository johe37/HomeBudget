from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .constants import (
    MANUAL,
    MORTGAGE_INTEREST,
    PARTNER_FUEL,
    PARTNER_LOAN,
    PRIMARY_FUEL,
    PRIMARY_INSURANCE,
    PRIMARY_LOAN,
)
from .forms import SwedishDecimalField
from .models import Expense, Income, Plan
from .services import summarize_plan, sync_derived


def post_plan(plan, **overrides):
    data = {
        "year": str(plan.year),
        "month": str(plan.month),
        "note": plan.note,
        "mortgage_balance": str(plan.mortgage_balance),
        "mortgage_rate_percent": str(plan.mortgage_rate * 100),
        "amortization_rate_percent": str(plan.amortization_rate * 100),
        "primary_loan": str(plan.primary_loan),
        "primary_insurance": str(plan.primary_insurance),
        "primary_fuel": str(plan.primary_fuel),
        "partner_loan": str(plan.partner_loan),
        "partner_insurance": str(plan.partner_insurance),
        "partner_fuel": str(plan.partner_fuel),
    }
    incomes = list(plan.incomes.all())
    data.update({
        "income-TOTAL_FORMS": str(len(incomes)),
        "income-INITIAL_FORMS": str(len(incomes)),
        "income-MIN_NUM_FORMS": "0",
        "income-MAX_NUM_FORMS": "200",
    })
    for index, income in enumerate(incomes):
        data[f"income-{index}-id"] = str(income.pk)
        data[f"income-{index}-kind"] = income.kind
        data[f"income-{index}-person"] = income.person
        data[f"income-{index}-gross"] = "" if income.gross is None else str(income.gross)
        data[f"income-{index}-tax_percent"] = "" if income.tax_rate is None else str(income.tax_rate * 100)
        data[f"income-{index}-net"] = str(income.net)
        if income.active:
            data[f"income-{index}-active"] = "on"
    expenses = list(plan.expenses.filter(source="manual"))
    data.update({
        "expense-TOTAL_FORMS": str(len(expenses)),
        "expense-INITIAL_FORMS": str(len(expenses)),
        "expense-MIN_NUM_FORMS": "0",
        "expense-MAX_NUM_FORMS": "200",
    })
    for index, expense in enumerate(expenses):
        data[f"expense-{index}-id"] = str(expense.pk)
        data[f"expense-{index}-name"] = expense.name
        data[f"expense-{index}-category"] = expense.category
        data[f"expense-{index}-person"] = expense.person
        data[f"expense-{index}-amount"] = str(expense.amount)
        data[f"expense-{index}-note"] = expense.note
        if expense.active:
            data[f"expense-{index}-active"] = "on"
    data.update(overrides)
    return data


class MoneyFieldTests(TestCase):
    def test_swedish_decimal_accepts_spaces_and_comma(self):
        field = SwedishDecimalField()
        self.assertEqual(field.clean("1 234,50"), Decimal("1234.50"))
        self.assertEqual(field.clean("1.250,50"), Decimal("1250.50"))
        optional = SwedishDecimalField(required=False)
        self.assertIsNone(optional.clean(""))
        self.assertIsNone(optional.clean("  "))


def sample_plan(user):
    """A made-up month. The figures are not from a real household."""
    home = user.household
    if not home.partner_name:
        home.partner_name = "Person 2"
        home.save()
    plan = Plan.objects.create(
        user=user,
        year=2026,
        month=3,
        mortgage_balance=Decimal("120000"),
        mortgage_rate=Decimal("0.03"),
        amortization_rate=Decimal("0.02"),
        primary_insurance=Decimal("100"),
        primary_fuel=Decimal("400"),
        partner_loan=Decimal("150"),
        partner_insurance=Decimal("80"),
    )
    Income.objects.create(plan=plan, kind="Lön", person=home.primary_name, net=Decimal("10000"), sort_order=0)
    Income.objects.create(plan=plan, kind="Lön", person=home.partner_name, net=Decimal("8000"), sort_order=1)
    Income.objects.create(plan=plan, kind="Bidrag", person=home.shared_name, net=Decimal("500"), sort_order=2)
    Expense.objects.create(
        plan=plan, name="Mat", category="Leva", person=home.shared_name,
        amount=Decimal("2000"), source=MANUAL, sort_order=100,
    )
    Expense.objects.create(
        plan=plan, name="Studielån", category="Lån", person=home.primary_name,
        amount=Decimal("300"), source=MANUAL, sort_order=101,
    )
    sync_derived(plan)
    return plan


class PlanMathTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="test-pass-123")
        self.plan = sample_plan(self.user)

    def test_totals_round_to_ore(self):
        summary = summarize_plan(self.plan)
        self.assertEqual(summary.income_total, Decimal("18500.00"))
        self.assertEqual(summary.expense_total, Decimal("3530.00"))
        self.assertEqual(summary.left, Decimal("14970.00"))
        self.assertEqual(summary.mortgage.interest, Decimal("300.00"))
        self.assertEqual(summary.mortgage.amortization, Decimal("200.00"))
        self.assertEqual(summary.mortgage.total, Decimal("500.00"))
        self.assertEqual(summary.cars[0].total, Decimal("500.00"))
        self.assertEqual(summary.cars[1].total, Decimal("230.00"))
        self.assertEqual(summary.car_total, Decimal("730.00"))

        interest = self.plan.expenses.get(source="mortgage_interest")
        amort = self.plan.expenses.get(source="mortgage_amortization")
        self.assertEqual(interest.amount, Decimal("300.00"))
        self.assertEqual(interest.person, "Gemensam")
        self.assertEqual(amort.amount, Decimal("200.00"))
        self.assertEqual(self.plan.expenses.get(source=PRIMARY_FUEL).person, "Person 1")
        self.assertFalse(Expense.objects.filter(plan=self.plan, source=PRIMARY_LOAN).exists())
        self.assertFalse(Expense.objects.filter(plan=self.plan, source=PARTNER_FUEL).exists())

        by_name = {row.category: row.amount for row in summary.categories}
        self.assertEqual(by_name["Boende"], Decimal("500.00"))
        self.assertEqual(by_name["Transport"], Decimal("730.00"))
        self.assertEqual(by_name["Leva"], Decimal("2000.00"))
        self.assertEqual(by_name["Lån"], Decimal("300.00"))
        self.assertEqual(by_name["Sparande"], Decimal("0.00"))

        people = {row.person: row for row in summary.people}
        self.assertEqual(people["Person 1"].net, Decimal("10000.00"))
        self.assertEqual(people["Person 1"].own_costs, Decimal("800.00"))
        self.assertEqual(people["Person 2"].net, Decimal("8000.00"))
        self.assertEqual(people["Person 2"].own_costs, Decimal("230.00"))
        self.assertEqual(people["Gemensam"].net, Decimal("500.00"))
        self.assertEqual(people["Gemensam"].own_costs, Decimal("2500.00"))
        self.assertEqual(people["Gemensam"].difference, Decimal("-2000.00"))

        sync_derived(self.plan)
        self.assertEqual(self.plan.expenses.filter(source=PRIMARY_INSURANCE).count(), 1)

    def test_inactive_income_is_excluded(self):
        income = self.plan.incomes.get(person="Person 2")
        income.active = False
        income.save()
        summary = summarize_plan(self.plan)
        self.assertEqual(summary.income_total, Decimal("10500.00"))

    def test_mortgage_and_cars_stay_separate(self):
        self.plan.primary_insurance = Decimal("999")
        self.plan.save()
        sync_derived(self.plan)
        self.assertEqual(self.plan.expenses.get(source=MORTGAGE_INTEREST).amount, Decimal("300.00"))
        self.assertEqual(self.plan.expenses.get(source=PRIMARY_INSURANCE).person, "Person 1")
        self.assertEqual(self.plan.expenses.get(source=PARTNER_LOAN).amount, Decimal("150.00"))

        self.plan.mortgage_balance = Decimal("0")
        self.plan.save()
        sync_derived(self.plan)
        self.assertFalse(self.plan.expenses.filter(source=MORTGAGE_INTEREST).exists())
        self.assertEqual(self.plan.expenses.get(source=PRIMARY_INSURANCE).amount, Decimal("999.00"))
        self.assertEqual(summarize_plan(self.plan).car_total, Decimal("1629.00"))

    def test_renaming_the_household_updates_derived_rows(self):
        home = self.user.household
        home.primary_name = "Alex"
        home.save()
        sync_derived(self.plan)
        self.assertEqual(self.plan.expenses.get(source=PRIMARY_INSURANCE).person, "Alex")
        self.assertEqual(self.plan.expenses.get(source=PRIMARY_FUEL).person, "Alex")
        self.assertEqual(self.plan.incomes.get(net=Decimal("10000.00")).person, "Person 1")

    def test_a_single_person_has_one_car(self):
        user = User.objects.create_user("solo", password="test-pass-123")
        self.assertEqual(user.household.partner_name, "")
        plan = Plan.objects.create(
            user=user,
            year=2026,
            month=6,
            mortgage_balance=Decimal("120000"),
            mortgage_rate=Decimal("0.03"),
            amortization_rate=Decimal("0.02"),
            primary_insurance=Decimal("100"),
            partner_loan=Decimal("150"),
        )
        sync_derived(plan)
        self.assertFalse(plan.expenses.filter(source=PARTNER_LOAN).exists())
        self.assertEqual(plan.expenses.get(source=MORTGAGE_INTEREST).person, "Gemensam")
        summary = summarize_plan(plan)
        self.assertEqual(len(summary.cars), 1)
        self.assertEqual(summary.car_total, Decimal("100.00"))
        self.assertNotIn("Person 2", [row.person for row in summary.people])

        self.client.force_login(user)
        page = self.client.get(reverse("plan_edit", args=[plan.pk]))
        self.assertContains(page, "id_primary_loan")
        self.assertNotContains(page, "id_partner_loan")
        self.assertContains(page, "hör till Person 1")


class AccountAndPlanFlowTests(TestCase):
    def test_anonymous_visitors_are_sent_to_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/accounts/login/?next=/")
        page = self.client.get("/accounts/login/")
        self.assertContains(page, "Logga in")
        self.assertContains(page, "Skapa konto")
        self.assertContains(page, "GitHub, Meta och X")

    def test_signup_opens_an_empty_archive(self):
        response = self.client.post("/accounts/signup/", {
            "username": "hushall",
            "password1": "en-bra-fras-2026",
            "password2": "en-bra-fras-2026",
        })
        self.assertRedirects(response, "/")
        page = self.client.get("/")
        self.assertContains(page, "Ingen månad ännu")
        home = User.objects.get(username="hushall").household
        self.assertEqual(home.primary_name, "Person 1")
        self.assertEqual(home.partner_name, "")

    def test_edit_copy_and_privacy(self):
        owner = User.objects.create_user("owner", password="test-pass-123")
        other = User.objects.create_user("other", password="test-pass-123")
        plan = sample_plan(owner)
        self.client.force_login(owner)
        page = self.client.get(reverse("plan_edit", args=[plan.pk]))
        self.assertContains(page, "10 000 kr")
        self.assertContains(page, "Bolån totalt")
        self.assertContains(page, "Bilar totalt")
        self.assertNotContains(page, "Tesla")
        self.assertNotContains(page, "Scenario")

        data = post_plan(plan)
        data["income-0-net"] = "12000"
        saved = self.client.post(reverse("plan_edit", args=[plan.pk]), data)
        self.assertRedirects(saved, reverse("plan_edit", args=[plan.pk]))
        plan.refresh_from_db()
        self.assertEqual(summarize_plan(plan).income_total, Decimal("20500.00"))

        copied = self.client.post(reverse("plan_copy", args=[plan.pk]))
        april = Plan.objects.get(user=owner, year=2026, month=4)
        self.assertRedirects(copied, reverse("plan_edit", args=[april.pk]))
        self.assertEqual(april.incomes.get(person="Person 1").net, Decimal("12000.00"))
        self.assertEqual(plan.incomes.get(person="Person 1").net, Decimal("12000.00"))

        self.client.force_login(other)
        hidden = self.client.get(reverse("plan_edit", args=[plan.pk]))
        self.assertEqual(hidden.status_code, 404)

        self.client.force_login(owner)
        removed = self.client.post(reverse("plan_delete", args=[april.pk]))
        self.assertRedirects(removed, reverse("dashboard"))
        self.assertFalse(Plan.objects.filter(pk=april.pk).exists())

    def test_empty_plan_shows_both_calculations_at_zero(self):
        user = User.objects.create_user("empty", password="test-pass-123")
        self.client.force_login(user)
        response = self.client.post(reverse("plan_create"), {"year": "2026", "month": "5"})
        plan = Plan.objects.get(user=user)
        self.assertRedirects(response, reverse("plan_edit", args=[plan.pk]))
        page = self.client.get(reverse("plan_edit", args=[plan.pk]))
        self.assertContains(page, "Bolån totalt")
        self.assertContains(page, "Bilar totalt")
        self.assertContains(page, "0 kr")
        self.assertNotContains(page, "Tesla")
        self.assertNotContains(page, "id_partner_loan")
        self.assertEqual(plan.expenses.count(), 0)

    def test_clearing_the_second_person_drops_their_car(self):
        user = User.objects.create_user("pair", password="test-pass-123")
        plan = sample_plan(user)
        self.client.force_login(user)
        saved = self.client.post(reverse("household"), {
            "primary_name": "Person 1",
            "partner_name": "  ",
            "shared_name": "Gemensam",
        })
        self.assertRedirects(saved, reverse("household"))
        plan.refresh_from_db()
        self.assertEqual(plan.partner_loan, 0)
        self.assertFalse(plan.expenses.filter(source=PARTNER_LOAN).exists())
        self.assertTrue(plan.incomes.filter(person="Person 2").exists())
        page = self.client.get(reverse("plan_edit", args=[plan.pk]))
        self.assertNotContains(page, "id_partner_loan")
        self.assertContains(page, "Person 2")

    def test_bad_amount_does_not_wipe_the_saved_month(self):
        user = User.objects.create_user("writer", password="test-pass-123")
        plan = sample_plan(user)
        self.client.force_login(user)
        data = post_plan(plan)
        data["income-0-net"] = "inte ett belopp"
        response = self.client.post(reverse("plan_edit", args=[plan.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rätta fälten")
        self.assertEqual(Income.objects.get(plan=plan, person="Person 1").net, Decimal("10000.00"))
