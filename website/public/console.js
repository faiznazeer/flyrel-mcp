const CHECK_MS = 620;
const SETTLE_MS = 1150;
const HOLD_MS = 4200;

const figure = document.getElementById("console");
const orders = [...figure.querySelectorAll(".order")];
const rules = [...figure.querySelectorAll(".rule")];
const wait = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

function hitRule(order) {
  for (const rule of rules) {
    rule.classList.remove("is-hit-allow", "is-hit-block", "is-hit-ask");
  }
  if (!order) return;
  const rule = rules.find((candidate) => candidate.dataset.rule === order.dataset.rule);
  const kind = ["allow", "block", "ask"].find((name) => order.classList.contains(`is-${name}`));
  rule?.classList.add(`is-hit-${kind}`);
}

// Replays the same synthetic list. Without this script, every verdict is simply shown.
async function play() {
  figure.classList.add("is-live");
  while (true) {
    for (const order of orders) order.classList.remove("is-checking", "is-decided");
    hitRule(null);
    await wait(500);
    for (const order of orders) {
      order.classList.add("is-checking");
      await wait(CHECK_MS);
      order.classList.remove("is-checking");
      order.classList.add("is-decided");
      hitRule(order);
      await wait(SETTLE_MS);
    }
    hitRule(null);
    await wait(HOLD_MS);
  }
}

const motion = matchMedia("(prefers-reduced-motion: no-preference)");
let started = false;
function maybeStart() {
  if (started || !motion.matches) return;
  started = true;
  play();
}
new IntersectionObserver(([entry], observer) => {
  if (!entry.isIntersecting) return;
  observer.disconnect();
  maybeStart();
}, { threshold: 0.25 }).observe(figure);
