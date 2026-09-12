/*
 * Creates an owner account with in-memory disposable credentials, then checks
 * registration and login in a fresh browser context. The generated values are
 * intentionally never printed or persisted.
 */

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const APP_URL = process.env.OPRYSKI_APP_URL || "https://jaunty-infamous-seal.anvil.app/";
const SCREENSHOT_DIR = process.env.OPRYSKI_SCREENSHOT_DIR || "/tmp/opryski-playwright-auth";
const suffix = `${Date.now()}-${crypto.randomBytes(6).toString("hex")}`;
const credentials = {
  email: `opryski-owner-${suffix}@example.com`,
  password: `Disposable-${suffix}-Aa9!`,
  fullName: "Testowy właściciel",
};

const { chromium } = require("playwright");

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

function safeError(error) {
  let message = String(error);
  for (const value of Object.values(credentials)) {
    if (value) message = message.split(value).join("[redacted]");
  }
  return message.slice(0, 300);
}

async function redactScreenshot(page, filePath) {
  await page.evaluate(({ email, password, fullName }) => {
    const replacements = [email, password, fullName].filter(Boolean);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node;
    while ((node = walker.nextNode())) nodes.push(node);
    for (const textNode of nodes) {
      let text = textNode.nodeValue || "";
      for (const value of replacements) text = text.split(value).join("[redacted]");
      textNode.nodeValue = text;
    }
    document.querySelectorAll("input, textarea").forEach((element) => {
      element.value = "";
      element.setAttribute("value", "");
      element.style.visibility = "hidden";
    });
  }, credentials);
  await page.addStyleTag({ content: "input, textarea { visibility: hidden !important; }" });
  await page.screenshot({ path: filePath, fullPage: true });
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--no-proxy-server"] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
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
  const screenshotPath = path.join(SCREENSHOT_DIR, "ephemeral-owner-auth.png");
  try {
    await page.goto(APP_URL, { waitUntil: "networkidle", timeout: 30000 });
    await fillInput(page, "Email", credentials.email, 0);
    await fillInput(page, "Hasło", credentials.password, 1);
    await fillInput(page, "Imię i nazwisko (rejestracja)", credentials.fullName, 2);
    await page.getByRole("button", { name: "Załóż konto właściciela", exact: true }).click();
    const confirmation = page.getByText("Konto właściciela utworzone. Możesz się teraz zalogować.", { exact: true });
    await confirmation.waitFor({ state: "visible", timeout: 15000 });
    const registrationText = await page.locator("body").innerText();
    if (/This app has experienced an error|ModuleNotFoundError|SecretError/i.test(registrationText)) {
      throw new Error("Anvil runtime or secret error is visible during registration");
    }
    await page.getByRole("button", { name: "Zaloguj", exact: true }).click();
    await page.getByRole("button", { name: "Panel", exact: true }).waitFor({ state: "visible", timeout: 15000 });
    if (await page.getByRole("button", { name: "Zaloguj", exact: true }).isVisible().catch(() => false)) {
      throw new Error("Owner login did not leave the login screen");
    }
    if (consoleErrors.length || pageErrors.length || failedRequests.length || httpErrors.length) {
      throw new Error("Browser reported console, page, request, or HTTP errors");
    }
    const desktopOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    if (desktopOverflow) throw new Error("Horizontal overflow is visible at desktop width");
    await redactScreenshot(page, screenshotPath);
    await page.setViewportSize({ width: 390, height: 844 });
    const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    if (mobileOverflow) throw new Error("Horizontal overflow is visible at mobile width");
    await redactScreenshot(page, path.join(SCREENSHOT_DIR, "ephemeral-owner-mobile-auth.png"));
    statusLine("ephemeral owner registration/login", "PASS", {
      console_errors: consoleErrors.length,
      page_errors: pageErrors.length,
      failed_requests: failedRequests.length,
      http_errors: httpErrors.length,
      screenshot: screenshotPath,
    });
  } catch (error) {
    await redactScreenshot(page, screenshotPath).catch(() => {});
    statusLine("ephemeral owner registration/login", "FAIL", {
    reason: safeError(error),
      console_errors: consoleErrors.length,
    page_errors: pageErrors.length,
    failed_requests: failedRequests.length,
    http_errors: httpErrors.length,
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
