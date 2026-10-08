from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .calc import compare_plans, scenario_baseline
from .constants import MANUAL
from .csvio import BudgetCsvError, export_plans, import_plans
from .forms import ExpenseFormSet, IncomeFormSet, PlanCreateForm, PlanForm
from .models import Plan
from .services import (
    clone_plan,
    create_empty_plan,
    create_sample_plan,
    save_tried_plan,
    suggested_copy_name,
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


def _chosen_plan(raw, plans_by_id):
    if raw in (None, ""):
        return None
    try:
        pk = int(raw)
    except (TypeError, ValueError):
        return None
    return plans_by_id.get(pk)


@login_required
def plan_compare(request):
    plans = list(
        Plan.objects.filter(user=request.user).prefetch_related("incomes", "expenses")
    )
    plans_by_id = {plan.pk: plan for plan in plans}
    if "fran" not in request.GET and "mot" not in request.GET and len(plans) >= 2:
        return redirect(f"{request.path}?fran={plans[0].pk}&mot={plans[1].pk}")
    left = _chosen_plan(request.GET.get("fran"), plans_by_id)
    right = _chosen_plan(request.GET.get("mot"), plans_by_id)
    notice = ""
    diff = None
    if left and right and left.pk == right.pk:
        notice = "Välj två olika budgetar."
    elif left and right:
        diff = compare_plans(
            left,
            right,
            list(left.incomes.all()),
            list(left.expenses.all()),
            list(right.incomes.all()),
            list(right.expenses.all()),
        )
    elif request.GET.get("fran") or request.GET.get("mot"):
        notice = "Välj två budgetar."
    return render(
        request,
        "budgets/compare.html",
        {
            "plans": plans,
            "left": left,
            "right": right,
            "diff": diff,
            "notice": notice,
        },
    )


@login_required
@require_POST
def plan_sample(request):
    plan = create_sample_plan(request.user)
    messages.success(request, f"{plan.title} är skapad med slumpad lön och vanliga kostnader.")
    return redirect("plan_edit", pk=plan.pk)


@login_required
def plan_create(request):
    form = PlanCreateForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["name"]
        source = form.cleaned_data["copy_from"]
        if source is None:
            plan = create_empty_plan(request.user, name)
        else:
            plan = clone_plan(source, name)
        messages.success(request, f"{plan.title} är skapad.")
        return redirect("plan_edit", pk=plan.pk)
    return render(request, "budgets/plan_form.html", {"form": form})


@login_required
def plan_edit(request, pk):
    plan = get_object_or_404(Plan, pk=pk, user=request.user)
    if request.method == "GET":
        sync_derived(plan)
    income_qs = plan.incomes.all()
    expense_qs = plan.expenses.filter(source=MANUAL)
    form = PlanForm(
        request.POST or None,
        instance=plan,
        user=request.user,
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
            "scenario": scenario_baseline(plan, plan.incomes.all(), plan.expenses.all()),
        },
    )


@login_required
@require_POST
def plan_scenario_save(request, pk):
    source = get_object_or_404(Plan, pk=pk, user=request.user)
    try:
        clone = save_tried_plan(
            source,
            request.POST.get("rate_micro", ""),
            request.POST.get("amort_micro", ""),
            request.POST.get("income_scale", ""),
            request.POST.get("expense_scale", ""),
        )
    except (TypeError, ValueError):
        messages.error(request, "Provet kunde inte sparas.")
        return redirect("plan_edit", pk=source.pk)
    messages.success(request, f"Sparade provet som {clone.title}.")
    return redirect("plan_edit", pk=clone.pk)


@login_required
@require_POST
def plan_copy(request, pk):
    source = get_object_or_404(Plan, pk=pk, user=request.user)
    clone = clone_plan(source, suggested_copy_name(request.user, source.name))
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
    return render(
        request,
        "budgets/plan_delete.html",
        {"plan": plan, "from_list": request.GET.get("fran") == "lista"},
    )


@login_required
def plan_export(request):
    plans = Plan.objects.filter(user=request.user).prefetch_related("incomes", "expenses")
    return _csv_response(export_plans(plans), "månadsbudgetar.csv")


@login_required
def plan_export_one(request, pk):
    plan = get_object_or_404(
        Plan.objects.prefetch_related("incomes", "expenses"),
        pk=pk,
        user=request.user,
    )
    return _csv_response(export_plans([plan]), f"{plan.name}.csv")


@login_required
@require_POST
def plan_import(request):
    upload = request.FILES.get("fil")
    if upload is None:
        messages.error(request, "Välj en csv-fil.")
        return redirect("dashboard")
    try:
        created = import_plans(request.user, upload.read())
    except BudgetCsvError as exc:
        messages.error(request, str(exc))
        return redirect("dashboard")
    if len(created) == 1:
        messages.success(request, f"Importerade {created[0].title}.")
    else:
        messages.success(request, f"Importerade {len(created)} månadsbudgetar.")
    return redirect("dashboard")


def _csv_response(payload: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(payload, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f"attachment; filename=\"manadsbudgetar.csv\"; filename*=UTF-8''{quote(filename)}"
    )
    return response
