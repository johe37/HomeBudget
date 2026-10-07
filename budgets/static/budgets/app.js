const SHEETS = ["indata", "manad", "oversikt", "om"];
const THEME_KEY = "hb-theme";

function storedTheme() {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch (error) {
    return null;
  }
}

function applyTheme(theme) {
  const dark = theme === "dark";
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", dark ? "#0d1210" : "#eef2ef");
  const button = document.querySelector("[data-theme-toggle]");
  if (button) {
    const label = dark ? "Byt till ljust läge" : "Byt till mörkt läge";
    button.setAttribute("aria-pressed", dark ? "true" : "false");
    button.setAttribute("aria-label", label);
    button.title = label;
  }
}

function activeTheme() {
  return storedTheme() || document.documentElement.getAttribute("data-theme") || "light";
}

function sheetFromLocation() {
  const name = location.hash.replace(/^#/, "");
  return SHEETS.includes(name) ? name : "indata";
}

function openSheet(name, record) {
  const id = SHEETS.includes(name) ? name : "indata";
  for (const sheet of SHEETS) {
    const section = document.getElementById(sheet);
    if (section) section.hidden = sheet !== id;
  }
  document.querySelectorAll(".sheets a").forEach((link) => {
    if (link.getAttribute("href") === `#${id}`) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  if (record && location.hash !== `#${id}`) history.pushState(null, "", `#${id}`);
  if (record) window.scrollTo(0, 0);
}

function formatMoney(raw) {
  const original = String(raw);
  const trimmed = original.trim();
  if (trimmed === "") return "";
  if (/[a-zåäö]/i.test(trimmed.replace(/kr/gi, ""))) return original;

  let text = trimmed.replace(/[\s\u00a0]/g, "").replace(/kr/gi, "").replace(/%/g, "");
  let negative = false;
  if (text.startsWith("-")) {
    negative = true;
    text = text.slice(1);
  }

  let wholeRaw = text;
  let fraction = null;
  if (text.includes(",")) {
    const comma = text.indexOf(",");
    wholeRaw = text.slice(0, comma).replace(/\./g, "");
    fraction = text.slice(comma + 1).replace(/\D/g, "").slice(0, 2);
  } else if (text.includes(".")) {
    const parts = text.split(".");
    const last = parts[parts.length - 1];
    const head = parts.slice(0, -1);
    const groupedThousands = parts.length > 2 || (
      last.length === 3 && head.every((part, index) => /^\d+$/.test(part) && (index === 0 ? part.length >= 1 : part.length === 3))
    );
    if (groupedThousands && last.length === 3) {
      wholeRaw = parts.join("");
    } else {
      wholeRaw = head.join("");
      fraction = last.replace(/\D/g, "").slice(0, 2);
    }
  }

  let whole = wholeRaw.replace(/\D/g, "").replace(/^0+(?=\d)/, "");
  if (whole === "") {
    if (fraction === null) return negative ? "-" : "";
    whole = "0";
  }
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const body = fraction === null ? grouped : `${grouped},${fraction}`;
  return negative ? `-${body}` : body;
}

function caretFromDigits(formatted, digits) {
  if (digits <= 0) return 0;
  let seen = 0;
  for (let index = 0; index < formatted.length; index += 1) {
    if (/\d/.test(formatted[index])) seen += 1;
    if (seen >= digits) return index + 1;
  }
  return formatted.length;
}

function formatMoneyInput(input) {
  if (!(input instanceof HTMLInputElement) || !input.classList.contains("money")) return;
  const formatted = formatMoney(input.value);
  if (formatted === input.value) return;
  const caret = input.selectionStart;
  const digitsBefore = (input.value.slice(0, caret ?? input.value.length).match(/\d/g) || []).length;
  input.value = formatted;
  if (document.activeElement === input && caret !== null) {
    const next = caretFromDigits(formatted, digitsBefore);
    input.setSelectionRange(next, next);
  }
}

function addRow(prefix) {
  const total = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
  const proto = document.getElementById(`${prefix}-empty`);
  const rows = document.getElementById(`${prefix}-rows`);
  if (!total || !proto || !rows) return;
  const index = Number(total.value);
  rows.insertAdjacentHTML("beforeend", proto.innerHTML.replaceAll("__prefix__", String(index)));
  total.value = String(index + 1);
  const field = rows.lastElementChild?.querySelector("input:not([type='hidden']), select");
  if (field) field.focus();
}

document.addEventListener("click", (event) => {
  const themeToggle = event.target.closest("[data-theme-toggle]");
  if (themeToggle) {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (error) {
      /* Valet gäller den här visningen om lagring är avstängd. */
    }
    applyTheme(next);
    return;
  }
  const tab = event.target.closest(".sheets a");
  if (tab) {
    event.preventDefault();
    openSheet(tab.getAttribute("href").replace(/^#/, ""), true);
    return;
  }
  const button = event.target.closest("[data-add-row]");
  if (!button) return;
  addRow(button.dataset.addRow);
});

document.addEventListener("input", (event) => {
  formatMoneyInput(event.target);
});

window.addEventListener("popstate", () => openSheet(sheetFromLocation(), false));

document.querySelectorAll("input.money").forEach((input) => formatMoneyInput(input));
openSheet(sheetFromLocation(), false);
applyTheme(activeTheme());
bootWhatIf();

function makeLever(id, labelText, min, max, step, value) {
  const wrap = document.createElement("div");
  wrap.className = "lever";
  const top = document.createElement("div");
  top.className = "lever-top";
  const label = document.createElement("label");
  label.htmlFor = id;
  label.textContent = labelText;
  const output = document.createElement("output");
  output.htmlFor = id;
  top.append(label, output);
  const input = document.createElement("input");
  input.type = "range";
  input.id = id;
  input.min = String(min);
  input.max = String(max);
  input.step = String(step);
  input.value = String(value);
  const hint = document.createElement("p");
  hint.className = "muted lever-hint";
  hint.id = `${id}-hint`;
  input.setAttribute("aria-describedby", hint.id);
  wrap.append(top, input, hint);
  return { wrap, input, output, hint };
}

function emptyNote(text) {
  const note = document.createElement("p");
  note.className = "muted";
  note.textContent = text;
  return note;
}

function bootWhatIf() {
  const dataNode = document.getElementById("om-baseline");
  const root = document.getElementById("om");
  if (!dataNode || !root || !window.WhatIf) return;
  let baseline;
  try {
    baseline = JSON.parse(dataNode.textContent);
  } catch (error) {
    return;
  }

  const saved = WhatIf.savedControls(baseline);
  const controls = {
    rateMicro: saved.rateMicro,
    amortMicro: saved.amortMicro,
    incomeScale: { ...saved.incomeScale },
    expenseScale: { ...saved.expenseScale },
  };
  const levers = [];
  const savedView = WhatIf.evaluate(baseline, saved);

  function addRate(parent, id, label, key) {
    const range = WhatIf.rateRange(saved[key]);
    const row = makeLever(id, label, range.min, range.max, range.step, range.value);
    row.input.addEventListener("input", () => {
      controls[key] = Number(row.input.value);
      paint();
    });
    parent.append(row.wrap);
    levers.push({
      input: row.input,
      resetValue: String(saved[key]),
      update(view) {
        const monthly = key === "rateMicro" ? view.interestOre : view.amortOre;
        const rate = WhatIf.formatRate(controls[key]);
        row.output.textContent = rate;
        row.hint.textContent = `${WhatIf.formatKr(monthly)} per månad · sparat ${WhatIf.formatRate(saved[key])}`;
        row.input.setAttribute("aria-valuetext", `${rate}, ${WhatIf.formatKr(monthly)} per månad`);
      },
    });
  }

  function addScale(parent, id, label, map, key, savedOre) {
    const row = makeLever(id, label, 0, 200, 5, 100);
    row.input.addEventListener("input", () => {
      map[key] = Number(row.input.value);
      paint();
    });
    parent.append(row.wrap);
    levers.push({
      input: row.input,
      resetValue: "100",
      update() {
        const scaled = WhatIf.scaleOre(savedOre, map[key]);
        row.output.textContent = WhatIf.formatKr(scaled);
        row.hint.textContent = `${map[key]} % · sparat ${WhatIf.formatKr(savedOre)}`;
        row.input.setAttribute("aria-valuetext", `${WhatIf.formatKr(scaled)}, ${map[key]} %`);
      },
    });
  }

  const mortgage = root.querySelector("[data-om='mortgage']");
  if (mortgage) {
    if (BigInt(baseline.balanceOre || 0) > 0n) {
      addRate(mortgage, "om-rate", "Ränta", "rateMicro");
      addRate(mortgage, "om-amort", "Amortering", "amortMicro");
    } else {
      mortgage.append(emptyNote("Bolåneskulden är 0 kr. Räntan ändrar inget förrän en skuld är sparad."));
    }
  }

  const expenseHost = root.querySelector("[data-om='expenses']");
  if (expenseHost) {
    if ((baseline.expenses || []).length) {
      baseline.expenses.forEach((row, index) => {
        addScale(
          expenseHost,
          `om-exp-${index}`,
          row.category || "Utan kategori",
          controls.expenseScale,
          row.category,
          row.ore,
        );
      });
    } else {
      expenseHost.append(emptyNote("Inga sparade kostnader att dra i."));
    }
  }

  const incomeHost = root.querySelector("[data-om='incomes']");
  if (incomeHost) {
    if ((baseline.incomes || []).length) {
      baseline.incomes.forEach((row, index) => {
        addScale(
          incomeHost,
          `om-inc-${index}`,
          row.person || "Övrig inkomst",
          controls.incomeScale,
          row.person,
          row.ore,
        );
      });
    } else {
      incomeHost.append(emptyNote("Inga sparade inkomster att dra i."));
    }
  }

  const fields = {
    left: root.querySelector("[data-om='left']"),
    delta: root.querySelector("[data-om='delta']"),
    income: root.querySelector("[data-om='income']"),
    expense: root.querySelector("[data-om='expense']"),
    savings: root.querySelector("[data-om='savings']"),
    yearLeft: root.querySelector("[data-om='year-left']"),
    yearInterest: root.querySelector("[data-om='year-interest']"),
    yearAmort: root.querySelector("[data-om='year-amort']"),
    yearDebt: root.querySelector("[data-om='year-debt']"),
    yearNote: root.querySelector("[data-om='year-note']"),
    bars: root.querySelector("[data-om='bars']"),
  };

  function paintBars(view) {
    if (!fields.bars) return;
    fields.bars.replaceChildren();
    if (!view.categories.length) {
      const item = document.createElement("li");
      item.className = "muted";
      item.textContent = "Inga kostnader i provet.";
      fields.bars.append(item);
      return;
    }
    for (const category of view.categories) {
      const item = document.createElement("li");
      const label = document.createElement("div");
      label.className = "bar-label";
      const name = document.createElement("span");
      name.textContent = category.category || "Utan kategori";
      const meta = document.createElement("span");
      meta.textContent = `${WhatIf.formatKr(category.ore)} · ${WhatIf.formatPercent(category.ore, view.expenseOre)}`;
      label.append(name, meta);
      const track = document.createElement("div");
      track.className = "track";
      track.setAttribute("aria-hidden", "true");
      const fill = document.createElement("span");
      fill.style.width = `${WhatIf.barPct(category.ore, view.expenseOre)}%`;
      track.append(fill);
      item.append(label, track);
      fields.bars.append(item);
    }
  }

  function paint() {
    const view = WhatIf.evaluate(baseline, controls);
    const delta = view.leftOre - savedView.leftOre;
    if (fields.left) {
      fields.left.textContent = WhatIf.formatKr(view.leftOre);
      fields.left.classList.toggle("pos", view.leftOre >= 0n);
      fields.left.classList.toggle("neg", view.leftOre < 0n);
    }
    if (fields.delta) {
      fields.delta.textContent = WhatIf.deltaText(delta);
      fields.delta.classList.toggle("pos", delta > 0n);
      fields.delta.classList.toggle("neg", delta < 0n);
    }
    if (fields.income) fields.income.textContent = WhatIf.formatKr(view.incomeOre);
    if (fields.expense) fields.expense.textContent = WhatIf.formatKr(view.expenseOre);
    if (fields.savings) fields.savings.textContent = WhatIf.formatPercent(view.leftOre, view.incomeOre);
    if (fields.yearLeft) fields.yearLeft.textContent = WhatIf.formatKr(view.year.leftOre);
    if (fields.yearInterest) fields.yearInterest.textContent = WhatIf.formatKr(view.year.interestOre);
    if (fields.yearAmort) fields.yearAmort.textContent = WhatIf.formatKr(view.year.amortOre);
    if (fields.yearDebt) fields.yearDebt.textContent = WhatIf.formatKr(view.year.balanceOre);
    if (fields.yearNote) {
      if (BigInt(baseline.balanceOre || 0) === 0n) {
        fields.yearNote.textContent = "Tolv likadana månader.";
      } else if (view.year.clearsDebt) {
        fields.yearNote.textContent = "Tolv likadana månader. Amorteringen löser skulden under året.";
      } else {
        fields.yearNote.textContent = "Tolv likadana månader. Skulden minskar med amorteringen.";
      }
    }
    for (const lever of levers) lever.update(view);
    paintBars(view);
    writeTrial();
  }

  const saveForm = root.querySelector("[data-om-save]");

  function trialChanged() {
    if (Number(controls.rateMicro) !== Number(saved.rateMicro)) return true;
    if (Number(controls.amortMicro) !== Number(saved.amortMicro)) return true;
    const scales = [...Object.values(controls.incomeScale), ...Object.values(controls.expenseScale)];
    return scales.some((value) => Number(value) !== 100);
  }

  function writeTrial() {
    if (!saveForm) return;
    saveForm.elements.rate_micro.value = String(controls.rateMicro);
    saveForm.elements.amort_micro.value = String(controls.amortMicro);
    saveForm.elements.income_scale.value = JSON.stringify(controls.incomeScale);
    saveForm.elements.expense_scale.value = JSON.stringify(controls.expenseScale);
    const button = saveForm.querySelector("button");
    if (button) button.disabled = !trialChanged();
  }

  const reset = root.querySelector("[data-om-reset]");
  if (reset) {
    reset.addEventListener("click", () => {
      controls.rateMicro = saved.rateMicro;
      controls.amortMicro = saved.amortMicro;
      for (const key of Object.keys(controls.incomeScale)) controls.incomeScale[key] = 100;
      for (const key of Object.keys(controls.expenseScale)) controls.expenseScale[key] = 100;
      for (const lever of levers) lever.input.value = lever.resetValue;
      paint();
    });
  }

  paint();
}

document.addEventListener("change", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement)) return;
  if (input.type === "file" && input.form?.classList.contains("import-form") && input.files?.length) {
    input.form.requestSubmit();
    return;
  }
  if (!input.classList.contains("active-toggle")) return;
  const row = input.closest("tr");
  if (row) row.classList.toggle("is-off", !input.checked);
});
