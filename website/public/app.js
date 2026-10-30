const $ = (id) => document.getElementById(id);
const selected = new Set();
let brokers = [];
const names = new Map([["other", "Other"]]);
const regions = ["Global", "North America", "Europe", "Asia", "Africa", "South America", "Oceania", "Middle East"];
const form = $("waitlist-form");
const toggle = $("broker-toggle");
const panel = $("broker-panel");
const submit = $("submit-button");
let submitting = false;

$("year").textContent = new Date().getFullYear();

function showError(message) {
  $("form-error").textContent = message;
  $("form-error").hidden = !message;
}

function setOpen(open, returnFocus = false) {
  panel.hidden = !open;
  toggle.setAttribute("aria-expanded", String(open));
  if (open) $("broker-search").focus();
  else if (returnFocus) toggle.focus();
}

function updateSelection(restoreId) {
  toggle.classList.toggle("has-selection", selected.size > 0);
  $("broker-summary").textContent = selected.size === 0 ? "Choose your brokers"
    : selected.size === 1 ? names.get([...selected][0]) : `${selected.size} brokers selected`;
  $("selection-count").textContent = `${selected.size} selected · up to 20`;
  $("other-check").checked = selected.has("other");
  $("other-field").hidden = !selected.has("other");
  $("other-broker").required = selected.has("other");
  const chips = $("selected-brokers");
  chips.replaceChildren();
  chips.hidden = selected.size === 0;
  for (const id of selected) {
    const chip = document.createElement("span");
    chip.className = "broker-chip";
    const label = document.createElement("span");
    label.textContent = names.get(id);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove ${names.get(id)}`);
    remove.addEventListener("click", () => {
      selected.delete(id);
      updateSelection();
      renderOptions();
      toggle.focus();
    });
    chip.append(label, remove);
    chips.append(chip);
  }
  for (const input of $("broker-options").querySelectorAll("input")) {
    input.checked = selected.has(input.value);
    input.disabled = submitting || (selected.size >= 20 && !input.checked);
  }
  $("other-check").disabled = submitting || (selected.size >= 20 && !selected.has("other"));
  if (restoreId) document.getElementById(restoreId)?.focus();
}

function choose(id, checked) {
  if (checked && selected.size >= 20) {
    showError("You can select up to 20 brokers.");
    updateSelection();
    return;
  }
  if (checked) selected.add(id);
  else selected.delete(id);
  showError("");
  updateSelection();
}

function renderOptions() {
  const query = $("broker-search").value.trim().toLocaleLowerCase();
  const region = $("broker-region").value;
  const matches = brokers.filter((broker) => (!region || broker.region === region || broker.region === "Global")
    && `${broker.name} ${broker.markets} ${broker.region}`.toLocaleLowerCase().includes(query));
  const container = $("broker-options");
  container.replaceChildren();
  for (const group of regions) {
    const entries = matches.filter((broker) => broker.region === group);
    if (!entries.length) continue;
    const heading = document.createElement("h3");
    heading.className = "region-heading";
    heading.textContent = group;
    container.append(heading);
    for (const broker of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const label = document.createElement("label");
      label.className = "broker-option";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = broker.id;
      checkbox.checked = selected.has(broker.id);
      checkbox.disabled = submitting || (selected.size >= 20 && !checkbox.checked);
      checkbox.addEventListener("change", () => choose(broker.id, checkbox.checked));
      const name = document.createElement("span");
      name.textContent = broker.name;
      label.append(checkbox, name);
      container.append(label);
    }
  }
  container.scrollTop = 0;
  $("no-results").hidden = matches.length > 0;
}

toggle.addEventListener("click", () => setOpen(panel.hidden));
$("broker-done").addEventListener("click", () => {
  setOpen(false, true);
  if (selected.has("other")) $("other-broker").focus();
});
$("broker-search").addEventListener("input", renderOptions);
$("broker-region").addEventListener("change", renderOptions);
$("other-check").addEventListener("change", (event) => choose("other", event.target.checked));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !panel.hidden) {
    event.preventDefault();
    setOpen(false, true);
  }
});
document.addEventListener("click", (event) => {
  if (!$("broker-picker").contains(event.target)) setOpen(false);
});
$("broker-picker").addEventListener("focusout", (event) => {
  if (event.relatedTarget && !$("broker-picker").contains(event.relatedTarget)) setOpen(false);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submitting) return;
  showError("");
  if (selected.size === 0) {
    showError("Choose at least one broker, or add yours with Other / not listed.");
    setOpen(true);
    return;
  }
  if (!form.reportValidity()) return;
  const payload = {
    email: $("email").value.trim(),
    brokers: [...selected],
    otherBroker: selected.has("other") ? $("other-broker").value.trim() : "",
    consent: $("consent").checked,
    website: $("website").value,
  };
  submitting = true;
  setOpen(false);
  const controls = [...form.querySelectorAll("input, button, select")];
  for (const control of controls) control.disabled = true;
  form.setAttribute("aria-busy", "true");
  submit.querySelector("span").textContent = "Joining…";
  try {
    const response = await fetch("/api/waitlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(15000),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "We couldn’t save your signup. Please try again.");
    form.hidden = true;
    document.querySelector(".form-heading").hidden = true;
    $("success-state").hidden = false;
    $("success-state").focus();
    form.reset();
    selected.clear();
  } catch (error) {
    showError(error.name === "TimeoutError" || error instanceof TypeError
      ? "Connection interrupted. Please try again — your details are still here."
      : error.message);
  } finally {
    submitting = false;
    for (const control of controls) control.disabled = false;
    updateSelection();
    form.removeAttribute("aria-busy");
    submit.querySelector("span").textContent = "Join the waitlist";
  }
});

try {
  const response = await fetch("/brokers.json");
  if (!response.ok) throw new Error("Catalog unavailable");
  brokers = await response.json();
  for (const broker of brokers) names.set(broker.id, broker.name);
  for (const region of regions) {
    const option = document.createElement("option");
    option.value = region;
    option.textContent = region;
    $("broker-region").append(option);
  }
  renderOptions();
  updateSelection();
  toggle.disabled = false;
  submit.disabled = false;
} catch {
  $("broker-summary").textContent = "Broker list unavailable";
  showError("We couldn’t load the broker list. Please refresh to try again.");
}
