import { expect, test } from "@playwright/test";

const broker = (page, name) => page.getByRole("checkbox", { name: new RegExp(`^${name}\\b`) });
const email = (page) => page.getByLabel("Your email", { exact: true });
const consent = (page) => page.getByRole("checkbox", { name: "Email me about Flyrel early access." });
const submit = (page) => page.getByRole("button", { name: "Join waitlist" });

test("searches worldwide, keeps multiple selections and captures a signup through the real Worker", async ({ page }) => {
  await page.goto("/");
  await page.locator("#broker-toggle").click();
  await expect(page.locator("#broker-search")).toBeFocused();
  await page.getByLabel("Search brokers or countries").fill("India");
  await broker(page, "Zerodha").check();
  await page.getByLabel("Search brokers or countries").fill("");
  await page.getByRole("button", { name: "Africa", exact: true }).click();
  await broker(page, "EasyEquities").check();
  await page.getByRole("button", { name: "South America", exact: true }).click();
  await broker(page, "Hapi").check();
  await expect(page.locator("#selection-count")).toHaveText("3 selected");
  await page.locator("#selection-count").click();
  await expect(page.locator("#broker-options .broker")).toHaveCount(3);
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.locator("#broker-dialog")).toBeHidden();
  await expect(page.locator("#broker-summary")).toHaveText("Zerodha +2");
  await email(page).fill(`browser-${Date.now()}@example.invalid`);
  await consent(page).check();
  const saved = page.waitForResponse((response) => response.url().endsWith("/api/waitlist"));
  await submit(page).click();
  expect((await saved).status()).toBe(200);
  await expect(page.getByRole("heading", { name: "You’re on the list." })).toBeVisible();
  await expect(page.locator("#success-state")).toBeFocused();
});

test("keyboard dismissal, unlisted brokers and removal work on mobile without sideways scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.locator("#broker-toggle").click();
  await page.getByLabel("Search brokers or countries").fill("not-a-broker");
  await expect(page.locator("#no-results")).toBeVisible();
  await page.getByRole("button", { name: "Add “not-a-broker” as your broker" }).click();
  await expect(page.getByLabel("Your broker’s name")).toHaveValue("not-a-broker");
  await expect(page.getByLabel("Your broker’s name")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator("#broker-dialog")).toBeHidden();
  await expect(page.locator("#broker-toggle")).toBeFocused();
  await expect(page.locator("#broker-summary")).toHaveText("Other");
  await page.locator("#broker-toggle").click();
  await page.getByRole("checkbox", { name: /^Other/ }).uncheck();
  await expect(page.getByLabel("Your broker’s name")).toBeHidden();
  await page.getByRole("button", { name: "Close broker list" }).click();
  await expect(page.locator("#broker-summary")).toHaveText("Your brokers");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/landing-mobile.png", fullPage: true });
});

test("caps selections at the Worker's limit of 20", async ({ page }) => {
  await page.goto("/");
  await page.locator("#broker-toggle").click();
  const options = page.locator("#broker-options .broker input");
  for (let index = 0; index < 20; index += 1) await options.nth(index).check();
  await expect(page.locator("#selection-count")).toHaveText("20 selected · 20 is the maximum");
  await expect(options.nth(20)).toBeDisabled();
  await options.nth(0).uncheck();
  await expect(options.nth(20)).toBeEnabled();
});

test("requires each field in turn and preserves entered data on server failure", async ({ page }) => {
  await page.goto("/");
  await submit(page).click();
  await expect(page.getByRole("alert")).toContainText("valid email");
  await email(page).fill("retry@example.invalid");
  await submit(page).click();
  await expect(page.locator("#broker-dialog")).toBeVisible();
  await broker(page, "Interactive Brokers").check();
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.getByRole("alert")).toBeHidden();
  await submit(page).click();
  await expect(page.getByRole("alert")).toContainText("early access");
  await consent(page).check();
  await page.route("**/api/waitlist", (route) => route.fulfill({
    status: 503, contentType: "application/json", body: JSON.stringify({ error: "Please try again shortly." }),
  }));
  await submit(page).click();
  await expect(page.getByRole("alert")).toHaveText("Please try again shortly.");
  await expect(email(page)).toHaveValue("retry@example.invalid");
  await expect(page.locator("#broker-summary")).toHaveText("Interactive Brokers");
  await expect(submit(page)).toBeEnabled();
  await expect(page.locator("#success-state")).toBeHidden();
});

test("desktop layout labels the concept, loads under the CSP and links to privacy", async ({ page }) => {
  const problems = [];
  page.on("console", (message) => { if (message.type() === "error") problems.push(message.text()); });
  page.on("pageerror", (error) => problems.push(String(error)));
  await page.setViewportSize({ width: 1440, height: 900 });
  const response = await page.goto("/");
  expect(response.headers()["content-security-policy"]).toContain("default-src 'self'");
  await expect(page.locator("#broker-toggle")).toBeEnabled();
  await expect(page.locator(".console-flag")).toHaveText(/Concept preview.*synthetic.*no live broker/);
  await expect(page.locator("#ticker-a span").first()).toBeAttached();
  expect(await page.evaluate(() => document.fonts.check('500 40px "Mona Sans"'))).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/landing-desktop.png" });
  await page.getByRole("link", { name: "Privacy", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "A little clarity on your data." })).toBeVisible();
  expect(problems).toEqual([]);
});

test("reduced motion shows every verdict at once and stops the broker ticker", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("#console")).not.toHaveClass(/is-live/);
  await page.locator("#console").scrollIntoViewIfNeeded();
  await expect(page.locator(".order .verdict").last()).toBeVisible();
  await expect(page.locator(".order").last()).toHaveCSS("opacity", "1");
  await expect(page.locator(".ticker-track").first()).toHaveCSS("animation-name", "none");
});
