from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.forms import BaseModelFormSet, modelformset_factory
from django.forms.formsets import DELETION_FIELD_NAME

from .constants import SWEDISH_MONTHS
from .models import Expense, Income, Plan


class SwedishDecimalField(forms.DecimalField):
    def __init__(self, *args, places=2, **kwargs):
        self.places = places
        kwargs.setdefault("decimal_places", places)
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault(
            "widget",
            forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}),
        )
        super().__init__(*args, **kwargs)

    def prepare_value(self, value):
        if value in (None, ""):
            return ""
        if isinstance(value, str):
            return value
        quantum = Decimal("1").scaleb(-self.places)
        quantized = Decimal(value).quantize(quantum)
        text = f"{quantized:.{self.places}f}".rstrip("0").rstrip(".").replace(".", ",")
        if self.places <= 2:
            text = _group_thousands(text)
        return text

    def to_python(self, value):
        if isinstance(value, str):
            cleaned = (
                value.replace("\u00a0", "")
                .replace(" ", "")
                .replace("kr", "")
                .replace("%", "")
                .strip()
            )
            if "," in cleaned and "." in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", ".")
            value = cleaned
        parsed = super().to_python(value)
        if parsed in (None, ""):
            return parsed
        quantum = Decimal("1").scaleb(-self.places)
        return parsed.quantize(quantum, rounding=ROUND_HALF_UP)


def _group_thousands(text: str) -> str:
    sign = ""
    if text.startswith("-"):
        sign, text = "-", text[1:]
    whole, separator, fraction = text.partition(",")
    chunks = []
    while whole:
        chunks.append(whole[-3:])
        whole = whole[:-3]
    grouped = " ".join(reversed(chunks))
    if separator:
        return f"{sign}{grouped},{fraction}"
    return f"{sign}{grouped}"


def _style_form(form):
    for _name, field in form.fields.items():
        css = field.widget.attrs.get("class", "")
        classes = [part for part in (*css.split(), "edit") if part]
        if isinstance(field, SwedishDecimalField):
            classes.append("num")
            if field.places <= 2:
                classes.append("money")
        field.widget.attrs["class"] = " ".join(dict.fromkeys(classes))


class PlanForm(forms.ModelForm):
    year = forms.IntegerField(
        label="År",
        min_value=2000,
        max_value=2100,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
    )
    month = forms.TypedChoiceField(label="Månad", coerce=int, choices=[])
    mortgage_balance = SwedishDecimalField(label="Bolåneskuld", min_value=0)
    mortgage_rate_percent = SwedishDecimalField(
        label="Ränta, procent per år",
        places=4,
        min_value=0,
        max_value=100,
    )
    amortization_rate_percent = SwedishDecimalField(
        label="Amortering, procent per år",
        places=4,
        min_value=0,
        max_value=100,
    )
    primary_loan = SwedishDecimalField(label="Billån", min_value=0)
    primary_insurance = SwedishDecimalField(label="Bilförsäkring", min_value=0)
    primary_fuel = SwedishDecimalField(label="Drivmedel", min_value=0)
    partner_loan = SwedishDecimalField(label="Billån", min_value=0)
    partner_insurance = SwedishDecimalField(label="Bilförsäkring", min_value=0)
    partner_fuel = SwedishDecimalField(label="Drivmedel", min_value=0)

    class Meta:
        model = Plan
        fields = [
            "year",
            "month",
            "note",
            "mortgage_balance",
            "primary_loan",
            "primary_insurance",
            "primary_fuel",
            "partner_loan",
            "partner_insurance",
            "partner_fuel",
        ]
        labels = {"note": "Anteckning"}

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["month"].choices = [(index, SWEDISH_MONTHS[index]) for index in range(1, 13)]
        if not self.is_bound:
            self.fields["mortgage_rate_percent"].initial = Decimal(self.instance.mortgage_rate or 0) * 100
            self.fields["amortization_rate_percent"].initial = (
                Decimal(self.instance.amortization_rate or 0) * 100
            )
        self.fields["note"].widget = forms.TextInput()
        _style_form(self)

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("year")
        month = cleaned.get("month")
        if year and month:
            clash = Plan.objects.filter(user=self.user, year=year, month=month)
            if self.instance.pk:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                self.add_error("month", "Den månaden finns redan.")
        return cleaned

    def save(self, commit=True):
        plan = super().save(commit=False)
        plan.user = self.user
        plan.mortgage_rate = Decimal(self.cleaned_data["mortgage_rate_percent"]) / Decimal(100)
        plan.amortization_rate = Decimal(self.cleaned_data["amortization_rate_percent"]) / Decimal(100)
        if commit:
            plan.save()
        return plan


class PlanCreateForm(forms.Form):
    year = forms.IntegerField(
        label="År",
        min_value=2000,
        max_value=2100,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
    )
    month = forms.TypedChoiceField(label="Månad", coerce=int)
    copy_from = forms.ModelChoiceField(
        label="Utgå från",
        queryset=Plan.objects.none(),
        required=False,
        empty_label="Tom månad",
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["month"].choices = [(index, SWEDISH_MONTHS[index]) for index in range(1, 13)]
        self.fields["copy_from"].queryset = Plan.objects.filter(user=user)
        _style_form(self)

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("year")
        month = cleaned.get("month")
        if year and month and Plan.objects.filter(user=self.user, year=year, month=month).exists():
            self.add_error("month", "Den månaden finns redan.")
        return cleaned


def _blank_row(cleaned, keys):
    return all(not cleaned.get(key) for key in keys)


class IncomeForm(forms.ModelForm):
    gross = SwedishDecimalField(label="Brutto", required=False)
    net = SwedishDecimalField(label="Netto", required=False)
    tax_percent = SwedishDecimalField(
        label="Skatt %",
        required=False,
        places=4,
        min_value=0,
        max_value=100,
    )

    class Meta:
        model = Income
        fields = ["kind", "person", "gross", "net", "active"]
        labels = {"kind": "Typ", "person": "Person", "active": "Aktiv"}

    def __init__(self, *args, plan=None, **kwargs):
        self.plan = plan
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.tax_rate is not None:
            self.fields["tax_percent"].initial = Decimal(self.instance.tax_rate) * 100
        if not self.instance.pk and not self.is_bound:
            self.fields["active"].initial = True
        for name, label in (
            ("kind", "Typ"),
            ("person", "Person"),
            ("gross", "Brutto"),
            ("tax_percent", "Skatt i procent"),
            ("net", "Netto"),
            ("active", "Aktiv"),
        ):
            self.fields[name].widget.attrs["aria-label"] = label
        self.fields["kind"].widget.attrs["list"] = "income-kinds"
        self.fields["kind"].widget.attrs["class"] = "wide"
        self.fields["active"].widget.attrs["class"] = "active-toggle"
        _style_form(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get(DELETION_FIELD_NAME):
            return cleaned
        cleaned["kind"] = (cleaned.get("kind") or "").strip()
        cleaned["person"] = (cleaned.get("person") or "").strip()
        if _blank_row(cleaned, ("kind", "person", "gross", "net", "tax_percent")):
            cleaned["empty"] = True
            return cleaned
        if not cleaned["kind"]:
            self.add_error("kind", "Fyll i typ.")
        return cleaned

    def save(self, commit=True):
        income = super().save(commit=False)
        if self.plan is not None:
            income.plan = self.plan
        tax = self.cleaned_data.get("tax_percent")
        income.tax_rate = None if tax is None else Decimal(tax) / Decimal(100)
        if income.gross is not None:
            income.gross = Decimal(income.gross).quantize(Decimal("0.01"))
        income.net = Decimal(income.net or 0).quantize(Decimal("0.01"))
        if commit:
            income.save()
        return income


class ExpenseForm(forms.ModelForm):
    amount = SwedishDecimalField(label="Belopp", required=False)

    class Meta:
        model = Expense
        fields = ["name", "category", "person", "amount", "note", "active"]
        labels = {
            "name": "Post",
            "category": "Kategori",
            "person": "Vem",
            "note": "Anteckning",
            "active": "Aktiv",
        }

    def __init__(self, *args, plan=None, **kwargs):
        self.plan = plan
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.is_bound:
            self.fields["active"].initial = True
        for name, label in (
            ("name", "Post"),
            ("category", "Kategori"),
            ("person", "Vem"),
            ("amount", "Belopp"),
            ("note", "Anteckning"),
            ("active", "Aktiv"),
        ):
            self.fields[name].widget.attrs["aria-label"] = label
        self.fields["name"].widget.attrs["class"] = "wide"
        self.fields["category"].widget.attrs["list"] = "categories"
        self.fields["active"].widget.attrs["class"] = "active-toggle"
        _style_form(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get(DELETION_FIELD_NAME):
            return cleaned
        for key in ("name", "category", "person", "note"):
            cleaned[key] = (cleaned.get(key) or "").strip()
        if _blank_row(cleaned, ("name", "category", "person", "amount", "note")):
            cleaned["empty"] = True
            return cleaned
        if not cleaned["name"]:
            self.add_error("name", "Fyll i post.")
        if not cleaned["category"]:
            self.add_error("category", "Fyll i kategori.")
        return cleaned

    def save(self, commit=True):
        expense = super().save(commit=False)
        if self.plan is not None:
            expense.plan = self.plan
        expense.amount = Decimal(expense.amount or 0).quantize(Decimal("0.01"))
        expense.source = expense.source or "manual"
        if commit:
            expense.save()
        return expense


class BaseLineFormSet(BaseModelFormSet):
    def __init__(self, *args, plan=None, sort_start=0, **kwargs):
        self.plan = plan
        self.sort_start = sort_start
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["plan"] = self.plan
        return kwargs

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if DELETION_FIELD_NAME in form.fields:
            form.fields[DELETION_FIELD_NAME].label = "Ta bort"
            form.fields[DELETION_FIELD_NAME].widget.attrs["aria-label"] = "Ta bort rad"

    def save(self, commit=True):
        saved = []
        order = 0
        for form in self.forms:
            cleaned = getattr(form, "cleaned_data", None) or {}
            if not cleaned or cleaned.get("empty"):
                if cleaned.get("empty") and form.instance.pk:
                    form.instance.delete()
                continue
            if cleaned.get(DELETION_FIELD_NAME):
                if form.instance.pk:
                    form.instance.delete()
                continue
            obj = form.save(commit=False)
            obj.sort_order = self.sort_start + order
            order += 1
            if commit:
                obj.save()
            saved.append(obj)
        return saved


IncomeFormSet = modelformset_factory(
    Income,
    form=IncomeForm,
    formset=BaseLineFormSet,
    extra=1,
    can_delete=True,
    max_num=200,
)
ExpenseFormSet = modelformset_factory(
    Expense,
    form=ExpenseForm,
    formset=BaseLineFormSet,
    extra=1,
    can_delete=True,
    max_num=200,
)
