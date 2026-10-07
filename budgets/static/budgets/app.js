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
  const button = event.target.closest("[data-add-row]");
  if (!button) return;
  addRow(button.dataset.addRow);
});

document.addEventListener("change", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || !input.classList.contains("active-toggle")) return;
  const row = input.closest("tr");
  if (row) row.classList.toggle("is-off", !input.checked);
});
