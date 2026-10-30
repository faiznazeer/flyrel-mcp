import { expect, test } from "@playwright/test";

test("searches worldwide, keeps multiple selections and captures a signup through the real Worker", async ({ page }) => {
  await page.goto("/");
  await page.locator("#broker-toggle").click();
  await page.getByLabel("Search brokers or countries").fill("India");
  await page.getByRole("checkbox", { name: "Zerodha", exact: true }).check();
  await page.getByLabel("Search brokers or countries").fill("");
  await page.getByLabel("Filter by region").selectOption("Africa");
  await page.getByRole("checkbox", { name: "EasyEquities", exact: true }).check();
  await page.getByLabel("Filter by region").selectOption("South America");
  await page.getByRole("checkbox", { name: "Hapi", exact: true }).check();
  await expect(page.locator("#selection-count")).toHaveText("3 selected · up to 20");
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.locator("#broker-summary")).toHaveText("3 brokers selected");
  await expect(page.locator("#selected-brokers")).toContainText("Zerodha");
  await page.getByLabel("Your email", { exact: true }).fill(`browser-${Date.now()}@example.invalid`);
  await page.getByRole("checkbox", { name: "Email me about Flyrel early access." }).check();
  const saved = page.waitForResponse((response) => response.url().endsWith("/api/waitlist"));
  await page.getByRole("button", { name: "Join the waitlist" }).click();
  expect((await saved).status()).toBe(200);
  await expect(page.getByRole("heading", { name: "You’re on the list." })).toBeVisible();
  await expect(page.locator("#success-state")).toBeFocused();
});

test("keyboard dismissal, removable chips, no results and Other work on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.locator("#broker-toggle").click();
  await expect(page.locator("#broker-search")).toBeFocused();
  await page.getByLabel("Search brokers or countries").fill("not-a-broker");
  await expect(page.locator("#no-results")).toBeVisible();
  await page.getByRole("checkbox", { name: "Other / not listed" }).check();
  await page.keyboard.press("Escape");
  await expect(page.locator("#broker-toggle")).toBeFocused();
  await expect(page.getByLabel("Your broker’s name")).toBeVisible();
  await page.getByLabel("Your broker’s name").fill("My local broker");
  await page.getByRole("button", { name: "Remove Other", exact: true }).click();
  await expect(page.getByLabel("Your broker’s name")).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/landing-mobile.png", fullPage: true });
});

test("requires broker selection and preserves entered data on server failure", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your email", { exact: true }).fill("retry@example.invalid");
  await page.getByRole("checkbox", { name: "Email me about Flyrel early access." }).check();
  await page.getByRole("button", { name: "Join the waitlist" }).click();
  await expect(page.getByRole("alert")).toContainText("Choose at least one broker");
  await page.getByRole("checkbox", { name: "Interactive Brokers", exact: true }).check();
  await page.getByRole("button", { name: "Done" }).click();
  await page.route("**/api/waitlist", (route) => route.fulfill({
    status: 503, contentType: "application/json", body: JSON.stringify({ error: "Please try again shortly." }),
  }));
  await page.getByRole("button", { name: "Join the waitlist" }).click();
  await expect(page.getByRole("alert")).toHaveText("Please try again shortly.");
  await expect(page.getByLabel("Your email", { exact: true })).toHaveValue("retry@example.invalid");
  await expect(page.locator("#broker-summary")).toHaveText("Interactive Brokers");
  await expect(page.getByRole("button", { name: "Join the waitlist" })).toBeEnabled();
  await expect(page.locator("#success-state")).toBeHidden();
});

test("desktop layout, privacy link and security headers", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const response = await page.goto("/");
  expect(response.headers()["content-security-policy"]).toContain("default-src 'self'");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.locator("#broker-toggle")).toBeEnabled();
  await page.screenshot({ path: "test-results/landing-desktop.png", fullPage: true });
  await page.getByRole("link", { name: "Privacy", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "A little clarity on your data." })).toBeVisible();
});
