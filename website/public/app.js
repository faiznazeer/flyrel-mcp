const MAX_BROKERS = 20;
const REGIONS = ["Global", "North America", "Europe", "Asia", "Africa", "South America", "Oceania", "Middle East"];

const $ = (id) => document.getElementById(id);
const form = $("waitlist-form");
const dialog = $("broker-dialog");
const toggle = $("broker-toggle");
const submit = $("submit-button");
const search = $("broker-search");
const selected = new Set();
const names = new Map([["other", "Other"]]);
let brokers = [];
let region = "All";
let submitting = false;

$("year").textContent = new Date().getFullYear();

function showError(message) {
  $("form-error").textContent = message;
  $("form-error").hidden = !message;
}

function summary() {
  const picks = [...selected].map((id) => names.get(id));
  if (picks.length === 0) return "Your brokers";
  if (picks.length === 1) return picks[0];
  return `${picks[0]} +${picks.length - 1}`;
}

function updateSelection() {
  const full = selected.size >= MAX_BROKERS;
  toggle.classList.toggle("has-selection", selected.size > 0);
  $("broker-summary").textContent = summary();
  $("selection-count").textContent = `${selected.size} selected${full ? " · 20 is the maximum" : ""}`;
  $("other-check").checked = selected.has("other");
  $("other-field").hidden = !selected.has("other");
  for (const input of dialog.querySelectorAll('input[type="checkbox"]')) {
    input.checked = selected.has(input.value);
    input.disabled = full && !input.checked;
  }
}

function choose(id, checked) {
  if (checked && selected.size >= MAX_BROKERS) return;
  if (checked) selected.add(id);
  else selected.delete(id);
  showError("");
  updateSelection();
}

function brokerRow(broker) {
  const label = document.createElement("label");
  label.className = "broker";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.value = broker.id;
  input.addEventListener("change", () => choose(broker.id, input.checked));
  const mono = document.createElement("span");
  mono.className = "broker-mono";
  mono.setAttribute("aria-hidden", "true");
  mono.textContent = broker.name.replace(/[^\p{L}\p{N}]/gu, "").charAt(0).toUpperCase();
  const text = document.createElement("span");
  text.className = "broker-text";
  const name = document.createElement("span");
  name.className = "broker-name";
  name.textContent = broker.name;
  const market = document.createElement("span");
  market.className = "broker-market";
  market.textContent = broker.markets;
  text.append(name, market);
  const check = document.createElement("span");
  check.className = "broker-check";
  check.setAttribute("aria-hidden", "true");
  check.innerHTML = '<svg viewBox="0 0 12 12"><path d="m2.5 6.5 2.3 2.3 4.7-5.3"/></svg>';
  label.append(input, mono, text, check);
  return label;
}

function matches(broker, query) {
  const inRegion = region === "All" || broker.region === region
    || (region === "Selected" && selected.has(broker.id));
  return inRegion && `${broker.name} ${broker.markets} ${broker.region}`.toLocaleLowerCase().includes(query);
}

function renderOptions() {
  const raw = search.value.trim();
  const query = raw.toLocaleLowerCase();
  const found = brokers.filter((broker) => matches(broker, query));
  const list = $("broker-options");
  list.replaceChildren();
  for (const group of REGIONS) {
    const entries = found.filter((broker) => broker.region === group);
    if (!entries.length) continue;
    const heading = document.createElement("h3");
    heading.className = "region-heading";
    heading.textContent = group;
    const grid = document.createElement("div");
    grid.className = "broker-grid";
    grid.append(...entries.map(brokerRow));
    list.append(heading, grid);
  }
  $("no-results").hidden = found.length > 0;
  $("no-results-text").textContent = raw ? `No match for “${raw}”.` : "Nothing selected yet.";
  $("add-other").hidden = !raw;
  $("add-other").textContent = `Add “${raw}” as your broker`;
  $("broker-list").scrollTop = 0;
  updateSelection();
}

function setRegion(name) {
  region = name;
  for (const tab of $("broker-regions").children) {
    tab.setAttribute("aria-pressed", String(tab.textContent === name));
  }
  $("selection-count").setAttribute("aria-pressed", String(name === "Selected"));
  renderOptions();
}

function renderTabs() {
  for (const name of ["All", ...REGIONS]) {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.textContent = name;
    tab.setAttribute("aria-pressed", String(name === region));
    tab.addEventListener("click", () => setRegion(name));
    $("broker-regions").append(tab);
  }
}

function openPicker(focusOther = false) {
  if (!dialog.open) dialog.showModal();
  (focusOther ? $("other-broker") : search).focus();
}

function closePicker() {
  dialog.close();
  if (selected.size > 0 && !$("email").value.trim()) $("email").focus();
}

toggle.addEventListener("click", () => openPicker());
$("broker-done").addEventListener("click", () => {
  if (selected.has("other") && !$("other-broker").value.trim()) {
    $("other-broker").focus();
    return;
  }
  closePicker();
});
$("picker-close").addEventListener("click", closePicker);
dialog.addEventListener("click", (event) => { if (event.target === dialog) closePicker(); });
search.addEventListener("input", renderOptions);
$("selection-count").addEventListener("click", () => setRegion(region === "Selected" ? "All" : "Selected"));
$("other-check").addEventListener("change", (event) => {
  choose("other", event.target.checked);
  if (event.target.checked) $("other-broker").focus();
});
$("add-other").addEventListener("click", () => {
  const name = search.value.trim();
  if (selected.size >= MAX_BROKERS && !selected.has("other")) return;
  $("other-broker").value = name.slice(0, 100);
  search.value = "";
  choose("other", true);
  renderOptions();
  $("other-broker").focus();
});

function validate() {
  const email = $("email");
  if (!email.value.trim() || !email.validity.valid) {
    email.focus();
    return "Enter a valid email address.";
  }
  if (selected.size === 0) {
    openPicker();
    return "Choose at least one broker, or add yours with Other / not listed.";
  }
  if (selected.has("other") && !$("other-broker").value.trim()) {
    openPicker(true);
    return "Add your broker’s name, or remove Other.";
  }
  if (!$("consent").checked) {
    $("consent").focus();
    return "Tick the box so we can email you about early access.";
  }
  return "";
}

function setBusy(busy) {
  submitting = busy;
  form.toggleAttribute("aria-busy", busy);
  submit.disabled = busy;
  toggle.disabled = busy;
  $("email").readOnly = busy;
  $("submit-label").textContent = busy ? "Joining…" : "Join waitlist";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submitting) return;
  const problem = validate();
  showError(problem);
  if (problem) return;
  setBusy(true);
  try {
    const response = await fetch("/api/waitlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: $("email").value.trim(),
        brokers: [...selected],
        otherBroker: selected.has("other") ? $("other-broker").value.trim() : "",
        consent: $("consent").checked,
        website: $("website").value,
      }),
      signal: AbortSignal.timeout(15000),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      showError(result.error || "We couldn’t save your signup. Please try again.");
      return;
    }
    form.hidden = true;
    $("success-state").hidden = false;
    $("success-state").focus();
  } catch {
    showError("Connection interrupted. Please try again; your details are still here.");
  } finally {
    setBusy(false);
  }
});

function fillTickers() {
  // A fixed stride through the region-ordered catalog mixes the world on each row.
  const shuffled = brokers
    .map((broker, index) => [(index * 67) % brokers.length, broker])
    .sort(([a], [b]) => a - b)
    .map(([, broker]) => broker);
  const half = Math.ceil(shuffled.length / 2);
  for (const [id, group] of [["ticker-a", shuffled.slice(0, half)], ["ticker-b", shuffled.slice(half)]]) {
    const track = $(id);
    for (let copy = 0; copy < 2; copy += 1) {
      const run = document.createElement("div");
      run.className = "ticker-run";
      for (const broker of group) {
        const item = document.createElement("span");
        item.textContent = broker.name;
        run.append(item);
      }
      track.append(run);
    }
  }
}

try {
  const response = await fetch("/brokers.json");
  if (!response.ok) throw new Error("Catalog unavailable");
  brokers = await response.json();
  for (const broker of brokers) names.set(broker.id, broker.name);
  $("broker-count").textContent = brokers.length;
  renderTabs();
  renderOptions();
  fillTickers();
  toggle.disabled = false;
  submit.disabled = false;
} catch {
  $("broker-summary").textContent = "Broker list unavailable";
  showError("We couldn’t load the broker list. Please refresh to try again.");
}
