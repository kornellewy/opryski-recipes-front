/*
 * Disposable authenticated smoke runner for the published Anvil app.
 *
 * Credentials are read from the process environment only. They are never
 * printed, written to disk, or included in screenshots. This runner checks
 * login and role routing; it deliberately does not invent API-side test data.
 * Use disposable accounts and run with Playwright supplied through NODE_PATH.
 */

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
  if (fallbackIndex >= await inputs.count()) {
    throw new Error(`Unable to locate ${label} input`);
  }
  await inputs.nth(fallbackIndex).fill(value);
}

function safeError(error, credentials) {
  let message = String(error);
  for (const value of credentials) {
    if (value) message = message.split(value).join("[redacted]");
  }
  return message.slice(0, 300);
}

async function redactScreenshot(page, filePath, credentials) {
  await page.evaluate(({ email, password }) => {
    const replacements = [email, password].filter(Boolean);
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
  }, { email: credentials[0], password: credentials[1] });
  await page.addStyleTag({
    content: "input, textarea { visibility: hidden !important; }",
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
    await fillInput(page, "Email", email, 0);
    await fillInput(page, "Hasło", password, 1);
    await page.getByRole("button", { name: "Zaloguj", exact: true }).click();
    const marker = role === "owner"
      ? page.getByRole("button", { name: "Panel", exact: true })
      : page.getByRole("button", { name: "Dziś", exact: true });
    await marker.waitFor({ state: "visible", timeout: 15000 });
    const bodyText = await page.locator("body").innerText();
    if (/This app has experienced an error|ModuleNotFoundError|SecretError/i.test(bodyText)) {
      throw new Error("Anvil runtime error screen is visible");
    }
    const loginButton = page.getByRole("button", { name: "Zaloguj", exact: true });
    if (await loginButton.isVisible().catch(() => false)) {
      throw new Error(`${role} login did not leave the login screen`);
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    if (overflow) throw new Error("Horizontal overflow is visible after login");
    if (consoleErrors.length || pageErrors.length || failedRequests.length || httpErrors.length) {
      throw new Error("Browser reported console, page, request, or HTTP errors");
    }
    await redactScreenshot(page, screenshotPath, [email, password]);
    statusLine(`${role} login (${viewport.label})`, "PASS", {
      title,
      console_errors: consoleErrors.length,
      page_errors: pageErrors.length,
      failed_requests: failedRequests.length,
      http_errors: httpErrors.length,
      screenshot: screenshotPath,
    });
  } catch (error) {
    await redactScreenshot(page, screenshotPath, [email, password]).catch(() => {});
    statusLine(`${role} login (${viewport.label})`, "FAIL", {
      reason: safeError(error, [email, password]),
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
  console.error("Playwright runner failed before role execution");
  process.exitCode = 1;
});
