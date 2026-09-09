/*
 * Disposable authenticated smoke runner for the published Anvil app.
 *
 * Credentials are read from the process environment only. They are never
 * printed, written to disk, or included in screenshots. This runner checks
 * login and role routing; it deliberately does not invent API-side test data.
 * Use disposable accounts and run with Playwright supplied through NODE_PATH.
 */

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const APP_URL = process.env.OPRYSKI_APP_URL || "https://jaunty-infamous-seal.anvil.app/";
const SCREENSHOT_DIR = process.env.OPRYSKI_SCREENSHOT_DIR || "/tmp/opryski-playwright-auth";

const required = [
  "OPRYSKI_OWNER_EMAIL",
  "OPRYSKI_OWNER_PASSWORD",
  "OPRYSKI_WORKER_EMAIL",
  "OPRYSKI_WORKER_PASSWORD",
];
const missing = required.filter((name) => !process.env[name]);
if (missing.length) {
  console.error(`Missing required environment variables: ${missing.join(", ")}`);
  process.exit(2);
}

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
  if (fallbackIndex >= await inputs.count()) {
    throw new Error(`Unable to locate ${label} input`);
  }
  await inputs.nth(fallbackIndex).fill(value);
}

async function redactScreenshot(page, filePath) {
  await page.addStyleTag({
    content: "input, textarea { filter: blur(10px) !important; }",
  });
  await page.screenshot({ path: filePath, fullPage: true });
}

async function runRole(browser, role, email, password, viewport) {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  const httpErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text().slice(0, 300));
  });
  page.on("pageerror", (error) => pageErrors.push(String(error).slice(0, 300)));
  page.on("requestfailed", (request) => failedRequests.push(request.method()));
  page.on("response", (response) => {
    if (response.status() >= 400) httpErrors.push(response.status());
  });

  const screenshotPath = path.join(SCREENSHOT_DIR, `${role}-${viewport.label}-auth.png`);
  try {
    await page.goto(APP_URL, { waitUntil: "networkidle", timeout: 30000 });
    const title = await page.title();
    if (title !== "Opryski Recipes") throw new Error(`Unexpected page title: ${title}`);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    if (overflow) throw new Error("Horizontal overflow is visible");
    await fillInput(page, "Email", email, 0);
    await fillInput(page, "Hasło", password, 1);
    await page.getByRole("button", { name: "Zaloguj", exact: true }).click();
    await page.waitForTimeout(1500);

    const bodyText = await page.locator("body").innerText();
    if (/This app has experienced an error|ModuleNotFoundError|SecretError/i.test(bodyText)) {
      throw new Error("Anvil runtime error screen is visible");
    }
    const roleMarker = role === "owner"
      ? /Panel|Właściciel gospodarstwa/i.test(bodyText)
      : /Dziś|Zadanie|Pracownik/i.test(bodyText);
    if (!roleMarker) throw new Error(`Expected ${role} role marker was not visible`);
    await redactScreenshot(page, screenshotPath);
    statusLine(`${role} login (${viewport.label})`, "PASS", {
      title,
      console_errors: consoleErrors.length,
      page_errors: pageErrors.length,
      failed_requests: failedRequests.length,
      http_errors: httpErrors.length,
      screenshot: screenshotPath,
    });
  } catch (error) {
    await redactScreenshot(page, screenshotPath).catch(() => {});
    statusLine(`${role} login (${viewport.label})`, "FAIL", {
      reason: String(error).slice(0, 300),
      console_errors: consoleErrors.length,
      page_errors: pageErrors.length,
      failed_requests: failedRequests.length,
      http_errors: httpErrors.length,
      screenshot: screenshotPath,
    });
    await context.close();
    return false;
  }
  await context.close();
  return true;
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--no-proxy-server"] });
  try {
    const viewports = [
      { label: "desktop", width: 1280, height: 900 },
      { label: "mobile", width: 390, height: 844 },
    ];
    const results = [];
    for (const viewport of viewports) {
      results.push(await runRole(browser, "owner", process.env.OPRYSKI_OWNER_EMAIL, process.env.OPRYSKI_OWNER_PASSWORD, viewport));
      results.push(await runRole(browser, "worker", process.env.OPRYSKI_WORKER_EMAIL, process.env.OPRYSKI_WORKER_PASSWORD, viewport));
    }
    process.exitCode = results.every(Boolean) ? 0 : 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(`Playwright runner failed: ${String(error).slice(0, 300)}`);
  process.exitCode = 1;
});
