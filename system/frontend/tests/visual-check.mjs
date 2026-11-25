/**
 * 视觉基线 / 回归截图。
 *
 * 对**构建产物**（vite preview）做 1920×1080 截图，并用 Playwright route
 * 把 /api/steps、/api/errors、/api/query 拦截成仓库里的契约与 SSE 夹具，
 * 不需要起后端。同时记录关键区块的 bounding box，供前后两次运行做几何对比。
 *
 * 用法：
 *   node tests/visual-check.mjs --out tests/__screenshots__/baseline
 *   BASE_URL=http://127.0.0.1:4173 npm run preview   # 另开一个终端
 */

import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright-core";

import { launchArgs, resolveChromePath } from "./chrome.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = join(HERE, "..");
const REPO_ROOT = join(FRONTEND_ROOT, "..");

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:4173";
const VIEWPORT = { width: 1920, height: 1080 };
const MOBILE_VIEWPORT = { width: 420, height: 900 };

function parseArgs(argv) {
  let out = join(HERE, "__screenshots__", "current");
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--out") out = argv[++index];
  }
  return { out };
}

const { out } = parseArgs(process.argv.slice(2));
mkdirSync(out, { recursive: true });

const contract = JSON.parse(
  readFileSync(join(FRONTEND_ROOT, "src", "generated", "contract.json"), "utf8"),
);
const fixtureDir = join(REPO_ROOT, "fixtures", "sse");

function errorTable() {
  const { version, classes, codes } = contract.errors;
  return {
    version,
    classes,
    codes: Object.entries(codes).map(([code, spec]) => ({ code, ...spec })),
  };
}

function loadFixture(id) {
  return JSON.parse(readFileSync(join(fixtureDir, `${id}.json`), "utf8"));
}

const executablePath = resolveChromePath();
if (!executablePath) {
  console.error("找不到 Chrome/Edge。请安装，或设置 CHROME_PATH=/path/to/chrome。");
  process.exit(2);
}

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: launchArgs(),
});

const page = await browser.newPage({ viewport: VIEWPORT });

await page.route("**/api/steps", (route) =>
  route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(contract.steps) }),
);
await page.route("**/api/errors", (route) =>
  route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(errorTable()) }),
);
await page.route("**/api/query", async (route) => {
  const body = route.request().postDataJSON();
  const query = typeof body?.query === "string" ? body.query : "";
  const match = /场景:([0-9A-Za-z_]+)/.exec(query);
  const fixture = match ? loadFixture(match[1]) : null;
  if (!fixture) {
    await route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({ detail: `没有回放夹具：${match?.[1] ?? "(none)"}` }),
    });
    return;
  }
  await route.fulfill({
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache",
      "X-Request-Id": `visual-${fixture.id}`,
    },
    body: fixture.frames.map((frame) => `${frame}\n\n`).join(""),
  });
});

/** 要对比的关键区块：选择器 + 期望存在性。 */
const AREAS = [
  [".app", true],
  [".masthead", true],
  [".layout", true],
  [".rail-panel", true],
  [".chat-panel", true],
  [".panel-head", true],
  [".rail-item", true],
  [".rail-marker", true],
  [".badge", true],
  [".composer", true],
  [".composer textarea", true],
  [".composer button[type=submit], .composer button", true],
  [".footer", true],
  [".query-bubble", false],
  [".table-wrap", false],
  [".result-actions", false],
  [".error-card", false],
  [".result-empty", false],
  [".empty-state", false],
  [".masthead h1", true],
  [".subtitle", true],
  [".panel-head h2", true],
  [".panel-note", true],
  [".rail-label", true],
  [".rail-status", true],
  [".rail-duration", false],
  [".empty-title", false],
  [".result-note", false],
  [".query-bubble", false],
  [".table-wrap thead th", false],
  [".table-wrap tbody td", false],
];

const STYLE_PROPS = [
  "fontFamily",
  "fontSize",
  "fontWeight",
  "lineHeight",
  "letterSpacing",
  "color",
  "backgroundColor",
  "borderRadius",
  "padding",
  "margin",
  "textAlign",
];

async function collectMetrics() {
  return page.evaluate(
    ({ areas, styleProps }) => {
      const rect = (element) => {
        const box = element.getBoundingClientRect();
        return {
          x: Math.round(box.x * 100) / 100,
          y: Math.round(box.y * 100) / 100,
          width: Math.round(box.width * 100) / 100,
          height: Math.round(box.height * 100) / 100,
        };
      };
      const boxes = {};
      const styles = {};
      for (const [selector] of areas) {
        const element = document.querySelector(selector);
        boxes[selector] = element ? rect(element) : null;
        if (element) {
          const computed = getComputedStyle(element);
          styles[selector] = Object.fromEntries(
            styleProps.map((property) => [property, computed[property]]),
          );
        }
      }
      return {
        viewport: { width: window.innerWidth, height: window.innerHeight },
        document: {
          scrollWidth: document.documentElement.scrollWidth,
          scrollHeight: document.documentElement.scrollHeight,
        },
        boxes,
        styles,
      };
    },
    { areas: AREAS, styleProps: STYLE_PROPS },
  );
}

async function settle() {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(80);
}

async function openApp() {
  await page.setViewportSize(VIEWPORT);
  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  await page.waitForFunction(
    () => document.querySelectorAll(".rail-item").length === 12,
    null,
    { timeout: 20_000 },
  );
  await settle();
}

async function ask(scenario) {
  await page.locator("textarea").fill(`场景:${scenario} 华北销售额`);
  await page.getByRole("button", { name: "提问", exact: true }).click();
}

async function capture(name) {
  const metrics = await collectMetrics();
  await page.screenshot({ path: join(out, `${name}.png`) });
  writeFileSync(join(out, `${name}.json`), `${JSON.stringify(metrics, null, 2)}\n`);
  console.log(`✓ ${name} -> ${join(out, `${name}.png`)}`);
  return metrics;
}

const summary = {};

try {
  await openApp();
  summary.idle = await capture("idle");

  await ask("happy");
  await page.waitForSelector("tbody tr", { timeout: 20_000 });
  await settle();
  summary.happy = await capture("happy");

  await openApp();
  await ask("sql_rejected");
  await page.locator(".error-card").waitFor({ state: "visible", timeout: 20_000 });
  await settle();
  summary.error = await capture("error");

  await openApp();
  await ask("empty_rows");
  await page.locator('[data-testid="result-empty"]').waitFor({ state: "visible", timeout: 20_000 });
  await settle();
  summary.empty = await capture("empty");

  // 窄屏响应式：不应出现横向滚动（对应 S7 UI 测试 F8）。
  await openApp();
  await ask("happy");
  await page.waitForSelector("tbody tr", { timeout: 20_000 });
  await page.setViewportSize(MOBILE_VIEWPORT);
  await settle();
  summary.mobile = await capture("mobile-happy");
  assert.ok(
    summary.mobile.document.scrollWidth <= MOBILE_VIEWPORT.width + 1,
    `420px 视口不应横向滚动（scrollWidth=${summary.mobile.document.scrollWidth}）`,
  );

  writeFileSync(join(out, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
  console.log(`\n全部截图写入 ${out}`);
} catch (error) {
  console.error(error);
  process.exitCode = 1;
} finally {
  await browser.close();
}
