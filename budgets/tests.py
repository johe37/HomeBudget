from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .constants import MANUAL, MORTGAGE_INTEREST
from .forms import SwedishDecimalField
from .models import Expense, Income, Plan
from .services import summarize_plan, sync_derived


def post_plan(plan, **overrides):
    data = {
        "name": plan.name,
        "note": plan.note,
        "mortgage_balance": str(plan.mortgage_balance),
        "mortgage_rate_percent": str(plan.mortgage_rate * 100),
        "amortization_rate_percent": str(plan.amortization_rate * 100),
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
        self.assertEqual(field.clean("4 300"), Decimal("4300.00"))
        self.assertEqual(field.clean("4 300,50"), Decimal("4300.50"))
        self.assertEqual(field.prepare_value(Decimal("4300")), "4 300")
        self.assertEqual(field.prepare_value(Decimal("4300.50")), "4 300,5")
        self.assertEqual(field.prepare_value(Decimal("120000")), "120 000")
        percent = SwedishDecimalField(places=4, max_value=100)
        self.assertEqual(percent.prepare_value(Decimal("3")), "3")
        self.assertEqual(percent.prepare_value(Decimal("3.5")), "3,5")
        optional = SwedishDecimalField(required=False)
        self.assertIsNone(optional.clean(""))
        self.assertIsNone(optional.clean("  "))


def sample_plan(user):
    """A made-up month. The figures are not from a real household."""
    plan = Plan.objects.create(
        user=user,
        name="Provbudget",
        mortgage_balance=Decimal("120000"),
        mortgage_rate=Decimal("0.03"),
        amortization_rate=Decimal("0.02"),
    )
    Income.objects.create(plan=plan, kind="Lön", person="Person 1", net=Decimal("10000"), sort_order=0)
    Income.objects.create(plan=plan, kind="Lön", person="Person 2", net=Decimal("8000"), sort_order=1)
    Income.objects.create(plan=plan, kind="Bidrag", person="", net=Decimal("500"), sort_order=2)
    Expense.objects.create(
        plan=plan, name="Mat", category="Leva", person="",
        amount=Decimal("2000"), source=MANUAL, sort_order=100,
    )
    Expense.objects.create(
        plan=plan, name="Studielån", category="Lån", person="Person 1",
        amount=Decimal("300"), source=MANUAL, sort_order=101,
    )
    Expense.objects.create(
        plan=plan, name="Bilförsäkring", category="Transport", person="",
        amount=Decimal("100"), source=MANUAL, sort_order=102,
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
        self.assertEqual(summary.expense_total, Decimal("2900.00"))
        self.assertEqual(summary.left, Decimal("15600.00"))
        self.assertEqual(summary.mortgage.interest, Decimal("300.00"))
        self.assertEqual(summary.mortgage.amortization, Decimal("200.00"))
        self.assertEqual(summary.mortgage.total, Decimal("500.00"))

        interest = self.plan.expenses.get(source="mortgage_interest")
        amort = self.plan.expenses.get(source="mortgage_amortization")
        self.assertEqual(interest.amount, Decimal("300.00"))
        self.assertEqual(interest.person, "")
        self.assertEqual(amort.amount, Decimal("200.00"))
        self.assertEqual(self.plan.expenses.get(name="Bilförsäkring").source, MANUAL)

        self.assertEqual(
            [row.category for row in summary.categories],
            ["Boende", "Transport", "Leva", "Lån"],
        )
        by_name = {row.category: row.amount for row in summary.categories}
        self.assertEqual(by_name["Boende"], Decimal("500.00"))
        self.assertEqual(by_name["Transport"], Decimal("100.00"))
        self.assertEqual(by_name["Leva"], Decimal("2000.00"))
        self.assertEqual(by_name["Lån"], Decimal("300.00"))

        people = {row.person: row for row in summary.people}
        self.assertEqual(people["Person 1"].net, Decimal("10000.00"))
        self.assertEqual(people["Person 1"].own_costs, Decimal("300.00"))
        self.assertEqual(people["Person 2"].net, Decimal("8000.00"))
        self.assertEqual(people["Person 2"].own_costs, Decimal("0.00"))
        self.assertNotIn("Gemensam", people)

        sync_derived(self.plan)
        self.assertEqual(self.plan.expenses.filter(source=MORTGAGE_INTEREST).count(), 1)

    def test_inactive_income_is_excluded(self):
        income = self.plan.incomes.get(person="Person 2")
        income.active = False
        income.save()
        summary = summarize_plan(self.plan)
        self.assertEqual(summary.income_total, Decimal("10500.00"))

    def test_a_written_cost_does_not_change_the_mortgage(self):
        insurance = self.plan.expenses.get(name="Bilförsäkring")
        insurance.amount = Decimal("999")
        insurance.save()
        sync_derived(self.plan)
        self.assertEqual(self.plan.expenses.get(source=MORTGAGE_INTEREST).amount, Decimal("300.00"))
        self.assertEqual(self.plan.expenses.get(name="Bilförsäkring").amount, Decimal("999.00"))

        self.plan.mortgage_balance = Decimal("0")
        self.plan.save()
        sync_derived(self.plan)
        self.assertFalse(self.plan.expenses.filter(source=MORTGAGE_INTEREST).exists())
        self.assertEqual(self.plan.expenses.get(name="Bilförsäkring").amount, Decimal("999.00"))

    def test_income_is_the_first_thing_to_fill_in(self):
        user = User.objects.create_user("solo", password="test-pass-123")
        plan = Plan.objects.create(
            user=user,
            name="Juni",
            mortgage_balance=Decimal("120000"),
            mortgage_rate=Decimal("0.03"),
            amortization_rate=Decimal("0.02"),
        )
        sync_derived(plan)
        self.assertEqual(plan.expenses.get(source=MORTGAGE_INTEREST).person, "")

        self.client.force_login(user)
        page = self.client.get(reverse("plan_edit", args=[plan.pk]))
        html = page.content.decode()
        self.assertLess(html.index('class="band">Namn'), html.index('class="band">Inkomster'))
        self.assertLess(html.index('class="band">Inkomster'), html.index('class="band">Kostnader'))
        self.assertLess(html.index('class="band">Kostnader'), html.index('class="band">Bolån'))
        self.assertNotContains(page, "Lägg till en bil till")
        self.assertNotContains(page, "En bil till")
        self.assertNotContains(page, "Bilar")
        self.assertNotContains(page, "id_primary_loan")
        self.assertNotContains(page, 'href="/hushall/"')
        self.assertNotContains(page, 'id="people"')
        self.assertNotContains(page, 'list="people"')
        self.assertContains(page, 'href="#indata"')
        self.assertContains(page, 'aria-current="page"')
        self.assertContains(page, 'id="manad" class="block" tabindex="-1" hidden')
        self.assertContains(page, 'id="oversikt" class="block" tabindex="-1" hidden')
        self.assertContains(page, "Namn")
        self.assertContains(page, "Kopiera")
        self.assertNotContains(page, "Namn på kopian")
        self.assertNotContains(page, "År och månad")
        self.assertNotContains(page, "Kopiera till nästa månad")
        self.assertContains(page, 'value="120 000"')
        self.assertContains(page, 'class="edit num money"')
        self.assertNotContains(page, 'type="number"')


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
        self.assertContains(page, "Månadsbudgetar")
        self.assertContains(page, "Ingen månadsbudget ännu")
        self.assertNotContains(page, "Arkiv")
        self.assertNotContains(page, 'href="/hushall/"')
        self.assertTrue(User.objects.filter(username="hushall").exists())

    def test_edit_copy_and_privacy(self):
        owner = User.objects.create_user("owner", password="test-pass-123")
        other = User.objects.create_user("other", password="test-pass-123")
        plan = sample_plan(owner)
        self.client.force_login(owner)
        listing = self.client.get(reverse("dashboard"))
        self.assertContains(listing, "Radera")
        self.assertNotContains(listing, "Ta bort")
        self.assertNotContains(listing, "Öppna")
        self.assertContains(listing, f"{reverse('plan_delete', args=[plan.pk])}?fran=lista")
        page = self.client.get(reverse("plan_edit", args=[plan.pk]))
        self.assertContains(page, "10 000 kr")
        self.assertContains(page, "Bolån totalt")
        self.assertNotContains(page, "Bilar")
        self.assertNotContains(page, "Tesla")
        self.assertNotContains(page, "Scenario")

        data = post_plan(plan)
        data["income-0-net"] = "12000"
        saved = self.client.post(reverse("plan_edit", args=[plan.pk]), data)
        self.assertRedirects(saved, reverse("plan_edit", args=[plan.pk]))
        plan.refresh_from_db()
        self.assertEqual(summarize_plan(plan).income_total, Decimal("20500.00"))

        copied = self.client.post(reverse("plan_copy", args=[plan.pk]))
        copy = Plan.objects.get(user=owner, name="Provbudget kopia")
        self.assertRedirects(copied, reverse("plan_edit", args=[copy.pk]))
        self.assertEqual(copy.incomes.get(person="Person 1").net, Decimal("12000.00"))
        self.assertEqual(plan.incomes.get(person="Person 1").net, Decimal("12000.00"))
        again = self.client.post(reverse("plan_copy", args=[copy.pk]))
        second = Plan.objects.get(user=owner, name="Provbudget kopia 2")
        self.assertRedirects(again, reverse("plan_edit", args=[second.pk]))
        second.delete()
        duplicate = self.client.post(reverse("plan_create"), {"name": "provbudget"})
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, "Det namnet finns redan.")
        self.assertEqual(Plan.objects.filter(user=owner).count(), 2)

        self.client.force_login(other)
        hidden = self.client.get(reverse("plan_edit", args=[plan.pk]))
        self.assertEqual(hidden.status_code, 404)

        self.client.force_login(owner)
        removed = self.client.post(reverse("plan_delete", args=[copy.pk]))
        self.assertRedirects(removed, reverse("dashboard"))
        self.assertFalse(Plan.objects.filter(pk=copy.pk).exists())

    def test_empty_plan_shows_both_calculations_at_zero(self):
        user = User.objects.create_user("empty", password="test-pass-123")
        self.client.force_login(user)
        response = self.client.post(reverse("plan_create"), {"name": "Tom budget"})
        plan = Plan.objects.get(user=user)
        self.assertRedirects(response, reverse("plan_edit", args=[plan.pk]))
        page = self.client.get(reverse("plan_edit", args=[plan.pk]))
        self.assertContains(page, "Bolån totalt")
        self.assertContains(page, "0 kr")
        self.assertNotContains(page, "Tesla")
        self.assertNotContains(page, "Bilar")
        self.assertNotContains(page, "Lägg till en bil till")
        html = page.content.decode()
        self.assertLess(html.index('class="band">Inkomster'), html.index('class="band">Kostnader'))
        self.assertEqual(plan.expenses.count(), 0)

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


class CsvTransferTests(TestCase):
    def test_export_and_import_round_trip(self):
        owner = User.objects.create_user("owner", password="test-pass-123")
        other = User.objects.create_user("other", password="test-pass-123")
        plan = sample_plan(owner)
        plan.note = "En anteckning"
        plan.save()
        plan.incomes.filter(person="Person 2").update(active=False)
        Expense.objects.create(
            plan=plan,
            name="=formel",
            category="Övrigt",
            person="",
            amount=Decimal("15.50"),
            note="Åäö",
            source=MANUAL,
            sort_order=103,
        )
        Plan.objects.create(user=other, name="Annan budget")

        self.client.force_login(owner)
        exported = self.client.get(reverse("plan_export"))
        self.assertEqual(exported.status_code, 200)
        self.assertIn("text/csv", exported["Content-Type"])
        text = exported.content.decode("utf-8-sig")
        self.assertIn("budget;rad;anteckning", text)
        self.assertIn("Provbudget;budget;En anteckning;120000;3;2", text)
        self.assertIn("Provbudget;inkomst;;;;;Lön;Person 1;;;10000;;;;1", text)
        self.assertNotIn("Bolån, ränta", text)
        self.assertNotIn("Annan budget", text)
        self.assertIn("'=formel", text)
        self.assertIn("15,5", text)

        one = self.client.get(reverse("plan_export_one", args=[plan.pk]))
        self.assertEqual(one.content, exported.content)
        hidden = self.client.get(reverse("plan_export_one", args=[Plan.objects.get(user=other).pk]))
        self.assertEqual(hidden.status_code, 404)

        blocked = self.client.post(
            reverse("plan_import"),
            {"fil": SimpleUploadedFile("b.csv", exported.content, content_type="text/csv")},
            follow=True,
        )
        self.assertContains(blocked, "Det namnet finns redan: Provbudget.")
        self.assertEqual(Plan.objects.filter(user=owner).count(), 1)

        fresh = User.objects.create_user("fresh", password="test-pass-123")
        self.client.force_login(fresh)
        imported = self.client.post(
            reverse("plan_import"),
            {"fil": SimpleUploadedFile("b.csv", exported.content, content_type="text/csv")},
            follow=True,
        )
        self.assertContains(imported, "Importerade Provbudget.")
        copy = Plan.objects.get(user=fresh)
        self.assertEqual(copy.note, "En anteckning")
        self.assertEqual(copy.mortgage_balance, Decimal("120000.00"))
        self.assertEqual(copy.mortgage_rate, Decimal("0.030000"))
        self.assertEqual(copy.incomes.get(person="Person 1").net, Decimal("10000.00"))
        self.assertFalse(copy.incomes.get(person="Person 2").active)
        self.assertEqual(copy.expenses.get(name="=formel").amount, Decimal("15.50"))
        self.assertEqual(copy.expenses.get(name="=formel").note, "Åäö")
        self.assertEqual(copy.expenses.get(source=MORTGAGE_INTEREST).amount, Decimal("300.00"))
        self.assertEqual(copy.expenses.get(source=MORTGAGE_INTEREST).person, "")

    def test_import_accepts_comma_files_and_rejects_a_bad_row(self):
        user = User.objects.create_user("comma", password="test-pass-123")
        self.client.force_login(user)
        payload = (
            "budget,rad,anteckning,bolåneskuld,ränta_procent,amortering_procent,"
            "typ,person,brutto,skatt_procent,netto,post,kategori,belopp,aktiv\n"
            "Sommar,budget,,0,0,0,,,,,,,,,\n"
            "Sommar,inkomst,,,,,Lön,P1,2000,25,1500,,,,1\n"
            "Sommar,kostnad,,,,,,P1,,,,Buss,Transport,40,1\n"
        ).encode()
        response = self.client.post(
            reverse("plan_import"),
            {"fil": SimpleUploadedFile("sommar.csv", payload, content_type="text/csv")},
            follow=True,
        )
        self.assertContains(response, "Importerade Sommar.")
        plan = Plan.objects.get(user=user, name="Sommar")
        self.assertEqual(plan.incomes.get().gross, Decimal("2000.00"))
        self.assertEqual(plan.incomes.get().tax_rate, Decimal("0.250000"))
        self.assertEqual(plan.incomes.get().net, Decimal("1500.00"))
        self.assertEqual(plan.expenses.get(source=MANUAL).amount, Decimal("40.00"))

        bad = (
            "budget;rad;bolåneskuld\n"
            "Trasig;budget;-5\n"
        ).encode()
        rejected = self.client.post(
            reverse("plan_import"),
            {"fil": SimpleUploadedFile("trasig.csv", bad, content_type="text/csv")},
            follow=True,
        )
        self.assertContains(rejected, "bolåneskulden kan inte vara negativ")
        self.assertFalse(Plan.objects.filter(user=user, name="Trasig").exists())
