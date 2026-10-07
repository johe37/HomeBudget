const SHEETS = ["indata", "manad", "oversikt"];
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
