/*
 * Creates an owner account with in-memory disposable credentials, then checks
 * registration and login in a fresh browser context. The generated values are
 * intentionally never printed or persisted.
 */

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const APP_URL = process.env.OPRYSKI_APP_URL || "https://jaunty-infamous-seal.anvil.app/";
const SCREENSHOT_DIR = process.env.OPRYSKI_SCREENSHOT_DIR || "/tmp/opryski-playwright-auth";
const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
const credentials = {
  email: `opryski-owner-${suffix}@example.invalid`,
  password: `Disposable-${suffix}-Aa9!`,
  fullName: "Testowy właściciel",
};

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true, mode: 0o700 });

function statusLine(label, status, extra = {}) {
  console.log(JSON.stringify({ label, status, ...extra }));
}

async function fillInput(page, label, value, fallbackIndex) {
  const labelled = page.getByLabel(label, { exact: true });
  if (await labelled.count()) {
    await labelled.first().fill(value);
    return;
  }
  const inputs = page.locator("input");
  await inputs.nth(fallbackIndex).fill(value);
}

async function redactScreenshot(page, filePath) {
  await page.addStyleTag({ content: "input, textarea { filter: blur(10px) !important; }" });
  await page.screenshot({ path: filePath, fullPage: true });
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--no-proxy-server"] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text().slice(0, 300));
  });
  page.on("pageerror", (error) => pageErrors.push(String(error).slice(0, 300)));
  page.on("requestfailed", (request) => failedRequests.push(request.method()));
  const screenshotPath = path.join(SCREENSHOT_DIR, "ephemeral-owner-auth.png");
  try {
    await page.goto(APP_URL, { waitUntil: "networkidle", timeout: 30000 });
    await fillInput(page, "Email", credentials.email, 0);
    await fillInput(page, "Hasło", credentials.password, 1);
    await fillInput(page, "Imię i nazwisko (rejestracja)", credentials.fullName, 2);
    await page.getByRole("button", { name: "Załóż konto właściciela", exact: true }).click();
    await page.waitForTimeout(1000);
    const registrationText = await page.locator("body").innerText();
    if (/This app has experienced an error|ModuleNotFoundError|SecretError/i.test(registrationText)) {
      throw new Error("Anvil runtime or secret error is visible during registration");
    }
    if (!/konto właściciela|utworzone|zalogować/i.test(registrationText)) {
      throw new Error("Registration confirmation was not visible");
    }
    await page.getByRole("button", { name: "Zaloguj", exact: true }).click();
    await page.waitForTimeout(1500);
    const loginText = await page.locator("body").innerText();
    if (!/Panel|Właściciel gospodarstwa/i.test(loginText)) {
      throw new Error("Owner dashboard marker was not visible after registration");
    }
    await redactScreenshot(page, screenshotPath);
    await page.setViewportSize({ width: 390, height: 844 });
    const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    if (mobileOverflow) throw new Error("Horizontal overflow is visible at mobile width");
    await redactScreenshot(page, path.join(SCREENSHOT_DIR, "ephemeral-owner-mobile-auth.png"));
    statusLine("ephemeral owner registration/login", "PASS", {
      console_errors: consoleErrors.length,
      page_errors: pageErrors.length,
      failed_requests: failedRequests.length,
      screenshot: screenshotPath,
    });
  } catch (error) {
    await redactScreenshot(page, screenshotPath).catch(() => {});
    statusLine("ephemeral owner registration/login", "FAIL", {
      reason: String(error).slice(0, 300),
      console_errors: consoleErrors.length,
      page_errors: pageErrors.length,
      failed_requests: failedRequests.length,
      screenshot: screenshotPath,
    });
    process.exitCode = 1;
  } finally {
    await context.close();
    await browser.close();
  }
})().catch((error) => {
  console.error(`Playwright runner failed: ${String(error).slice(0, 300)}`);
  process.exitCode = 1;
});
