from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .constants import MANUAL
from .forms import ExpenseFormSet, HouseholdForm, IncomeFormSet, PlanCreateForm, PlanForm
from .models import Plan
from .services import (
    clone_plan,
    create_empty_plan,
    household_for,
    month_title,
    next_month,
    next_open_month,
    summarize_plan,
    sync_derived,
)


@login_required
def dashboard(request):
    plans = list(
        Plan.objects.filter(user=request.user).prefetch_related("incomes", "expenses")
    )
    rows = [(plan, summarize_plan(plan)) for plan in plans]
    return render(
        request,
        "budgets/dashboard.html",
        {"rows": rows, "latest": rows[0] if rows else None},
    )


@login_required
def household_edit(request):
    household = household_for(request.user)
    form = HouseholdForm(request.POST or None, instance=household)
    if request.method == "POST" and form.is_valid():
        household = form.save()
        plans = Plan.objects.filter(user=request.user)
        if not household.partner_name:
            plans.update(partner_loan=0, partner_insurance=0, partner_fuel=0)
        for plan in plans:
            sync_derived(plan)
        messages.success(request, "Namnen är sparade.")
        return redirect("household")
    return render(request, "budgets/household.html", {"form": form})


@login_required
def plan_create(request):
    year, month = next_open_month(request.user)
    form = PlanCreateForm(
        request.POST or None,
        user=request.user,
        initial={"year": year, "month": month},
    )
    if request.method == "POST" and form.is_valid():
        chosen_year = form.cleaned_data["year"]
        chosen_month = form.cleaned_data["month"]
        source = form.cleaned_data["copy_from"]
        if source is None:
            plan = create_empty_plan(request.user, chosen_year, chosen_month)
        else:
            plan = clone_plan(source, chosen_year, chosen_month)
        messages.success(request, f"{plan.title} är skapad.")
        return redirect("plan_edit", pk=plan.pk)
    return render(request, "budgets/plan_form.html", {"form": form})


@login_required
def plan_edit(request, pk):
    plan = get_object_or_404(Plan, pk=pk, user=request.user)
    household = household_for(request.user)
    if request.method == "GET":
        sync_derived(plan)
    income_qs = plan.incomes.all()
    expense_qs = plan.expenses.filter(source=MANUAL)
    form = PlanForm(
        request.POST or None,
        instance=plan,
        user=request.user,
        household=household,
    )
    income_formset = IncomeFormSet(
        request.POST or None,
        queryset=income_qs,
        plan=plan,
        prefix="income",
    )
    expense_formset = ExpenseFormSet(
        request.POST or None,
        queryset=expense_qs,
        plan=plan,
        sort_start=100,
        prefix="expense",
    )
    if request.method == "POST" and form.is_valid() and income_formset.is_valid() and expense_formset.is_valid():
        with transaction.atomic():
            plan = form.save()
            income_formset.plan = plan
            expense_formset.plan = plan
            income_formset.save()
            expense_formset.save()
            sync_derived(plan)
        messages.success(request, f"{plan.title} är sparad.")
        return redirect("plan_edit", pk=plan.pk)
    summary = summarize_plan(plan)
    return render(
        request,
        "budgets/plan_edit.html",
        {
            "plan": plan,
            "form": form,
            "income_formset": income_formset,
            "expense_formset": expense_formset,
            "summary": summary,
        },
    )


@login_required
@require_POST
def plan_copy(request, pk):
    source = get_object_or_404(Plan, pk=pk, user=request.user)
    year, month = next_month(source.year, source.month)
    if Plan.objects.filter(user=request.user, year=year, month=month).exists():
        messages.error(request, f"{month_title(year, month)} finns redan.")
        return redirect("plan_edit", pk=source.pk)
    clone = clone_plan(source, year, month)
    messages.success(request, f"Kopierade till {clone.title}.")
    return redirect("plan_edit", pk=clone.pk)


@login_required
def plan_delete(request, pk):
    plan = get_object_or_404(Plan, pk=pk, user=request.user)
    if request.method == "POST":
        title = plan.title
        plan.delete()
        messages.success(request, f"{title} är raderad.")
        return redirect("dashboard")
    return render(request, "budgets/plan_delete.html", {"plan": plan})
