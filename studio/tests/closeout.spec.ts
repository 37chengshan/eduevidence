import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const id = "example--ai-coding-assistant-evidence";
const project = (tab: string) => `/studio/#/project/${id}/${tab}`;
const output = "test-results/closeout";

test("ambient motion is bounded, settles, preserves clicks and respects reduced motion", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = window.requestAnimationFrame.bind(window);
    (window as any).animationFrames = 0;
    window.requestAnimationFrame = (callback) =>
      original((time) => {
        (window as any).animationFrames++;
        callback(time);
      });
  });
  await page.goto(project("overview"));
  await expect(page.locator("main h1")).toBeVisible();
  const field = page.locator(".ambient-field");
  const glow = page.locator(".ambient-glow");
  await expect(field).toHaveAttribute("aria-hidden", "true");
  expect(await field.evaluate((e) => getComputedStyle(e).pointerEvents)).toBe(
    "none",
  );
  const canvas = field.locator("canvas");
  const before = await canvas.evaluate((e: HTMLCanvasElement) => e.toDataURL());
  await page.mouse.move(110, 630);
  await expect
    .poll(() => canvas.evaluate((e: HTMLCanvasElement) => e.toDataURL()))
    .not.toBe(before);
  await expect(field).toHaveAttribute("data-motion", "idle");
  const initialHeading = await page.locator("main h1").boundingBox();
  const client = await page.context().newCDPSession(page);
  await client.send("Performance.enable");
  const start = await client.send("Performance.getMetrics");
  await page.mouse.move(420, 150);
  for (let n = 0; n < 30; n++)
    await page.mouse.move(400 + n * 24, 150 + (n % 8) * 35);
  await expect(glow).toHaveAttribute("data-motion", "idle");
  expect(await glow.evaluate((e) => Number(getComputedStyle(e).opacity))).toBe(
    1,
  );
  expect(await page.locator("main h1").boundingBox()).toEqual(initialHeading);
  const frames = await page.evaluate(() => (window as any).animationFrames);
  await page.waitForTimeout(400); // Sample a genuinely idle interval, not just a DOM flag.
  expect(await page.evaluate(() => (window as any).animationFrames)).toBe(
    frames,
  );
  const end = await client.send("Performance.getMetrics");
  mkdirSync(output, { recursive: true });
  writeFileSync(
    `${output}/motion-performance.json`,
    JSON.stringify(
      { start, end, idleFrames: frames, idleFramesAfter400ms: frames },
      null,
      2,
    ),
  );
  await page.screenshot({ path: `${output}/ambient-active.png` });
  await page.getByRole("link", { name: "证据工作台", exact: true }).click();
  await expect(page.locator(".evidence-table")).toBeVisible();
  await page.mouse.move(110, 250);
  await expect(glow).toHaveCSS("opacity", "0");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(field).toHaveAttribute("data-motion-mode", "static");
  const still = await canvas.evaluate((e: HTMLCanvasElement) => e.toDataURL());
  await page.mouse.move(100, 650);
  await page.mouse.move(120, 580);
  await expect(field).toHaveAttribute("data-motion", "idle");
  expect(await canvas.evaluate((e: HTMLCanvasElement) => e.toDataURL())).toBe(
    still,
  );
  await page.mouse.move(750, 450);
  await expect(glow).toHaveCSS("opacity", "0");
  await client.detach();
});

test("touch keeps decoration static and mobile navigation works", async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
  });
  const page = await context.newPage();
  await page.goto(
    `http://127.0.0.1:${process.env.STUDIO_TEST_PORT || 8765}/studio/`,
  );
  await page.locator(".mobile-menu").click();
  await expect(page.locator(".sidebar")).toHaveClass(/is-open/);
  await page.getByRole("link", { name: "流程导览", exact: true }).click();
  await expect(page.locator("main h1")).toBeVisible();
  await expect(page.locator(".ambient-glow")).toHaveCSS("opacity", "0");
  await context.close();
});

for (const width of [320, 390, 768, 1440]) {
  for (const appearance of ["light", "dark"]) {
    test(`critical pages at ${width}px ${appearance}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((mode) => {
        if (window === window.top)
          localStorage.setItem("studio-appearance", mode);
      }, appearance);
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.goto(project("overview"));
      // Wait for React's theme effect instead of toggling during initialization.
      await expect(page.locator("html")).toHaveAttribute("data-appearance", appearance);
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      for (const tab of [
        "overview",
        "evidence",
        "graph",
        "activity",
        "revisions",
        "reports",
      ]) {
        await page.goto(project(tab));
        await expect(page.locator("main h1")).toBeVisible();
        await expect(page.locator("html")).toHaveAttribute("data-appearance", appearance);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 1,
          ),
        ).toBeTruthy();
        mkdirSync(output, { recursive: true });
        await page.screenshot({
          path: `${output}/${tab}-${width}-${appearance}.png`,
          fullPage: true,
        });
        if (tab === "overview" && process.env.STUDIO_VISUAL_BASELINE === "1") {
          await expect(page).toHaveScreenshot(
            `overview-${width}-${appearance}.png`,
            { fullPage: true, animations: "disabled" },
          );
        }
      }
      if (width === 390 || width === 1440) {
        for (const route of ["projects", "reports", "evolution", "guide"]) {
          await page.goto(`/studio/#/${route}`);
          await expect(page.locator("main h1")).toBeVisible();
          expect(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= innerWidth + 1,
            ),
          ).toBeTruthy();
          const scan = await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze();
          expect(
            scan.violations.filter((v) =>
              ["critical", "serious"].includes(v.impact || ""),
            ),
          ).toEqual([]);
        }
      }
      expect(errors).toEqual([]);
    });
  }
}

test("all downloaded report themes remain readable without network or JavaScript", async ({
  page,
  browser,
}, info) => {
  for (const theme of [
    "claude",
    "academic",
    "datalab",
    "datalab-dark",
    "presentation",
  ]) {
    const response = await page.request.get(
      `/api/studio/projects/${id}/report?theme=${theme}`,
    );
    expect(response.ok()).toBeTruthy();
    const file = info.outputPath(`${theme}.html`);
    writeFileSync(file, await response.body());
    const context = await browser.newContext({
      javaScriptEnabled: false,
      offline: true,
    });
    const offline = await context.newPage();
    await offline.goto(pathToFileURL(file).href);
    await expect(offline.locator("h1").first()).toBeVisible();
    expect((await offline.locator("body").innerText()).length).toBeGreaterThan(
      1000,
    );
    await context.close();
  }
});

test("selected graph traces the full authored chain without a mouse focus box", async ({
  page,
}) => {
  await page.goto(project("graph"));
  const node = page.locator(".graph-node.source").first();
  await node.click();
  await expect(node).toHaveClass(/selected/);
  expect(await node.evaluate((e) => getComputedStyle(e).outlineStyle)).toBe(
    "none",
  );
  await expect(
    page.locator('.graph-node.claim[opacity="1"]').first(),
  ).toBeVisible();
  const paths = page.locator(".graph-flow");
  await expect(paths.first()).toBeAttached();
  const before = await paths
    .first()
    .evaluate((e) => getComputedStyle(e).strokeDashoffset);
  await expect
    .poll(() =>
      paths.first().evaluate((e) => getComputedStyle(e).strokeDashoffset),
    )
    .not.toBe(before);
  await page.getByRole("button", { name: "暂停连线流动", exact: true }).click();
  await expect(paths).toHaveCount(0);
  await page.keyboard.press("Tab");
  await page.getByRole("button", { name: "播放连线流动", exact: true }).focus();
  await page.keyboard.press("Space");
  await expect(paths.first()).toBeAttached();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(paths).toHaveCount(0);
});

test("workplace demo is policy, source-backed, and animates in overview and reports", async ({
  page,
  request,
}) => {
  const key = "example--workplace-ai-assistant";
  const detail = await (
    await request.get(`/api/studio/projects/${key}`)
  ).json();
  expect(detail.project.domain).toBe("policy");
  expect(detail.evidence).toHaveLength(4);
  expect(detail.sources).toHaveLength(3);
  expect(detail.runs).toHaveLength(0);
  await page.goto(`/studio/#/project/${key}/overview`);
  const graph = page.locator(".graph-panel.compact");
  await graph.scrollIntoViewIfNeeded();
  await expect(graph.locator(".graph-flow").first()).toBeAttached();
  await graph
    .getByRole("button", { name: "暂停连线流动", exact: true })
    .click();
  await expect(graph.locator(".graph-flow")).toHaveCount(0);
  await page.goto(`/studio/#/project/${key}/reports`);
  await expect(page.locator(".theme-card")).toHaveCount(5);
  for (const theme of [
    "claude",
    "academic",
    "datalab",
    "datalab-dark",
    "presentation",
  ]) {
    await page.locator(`.theme-card.theme-${theme}`).click();
    const frame = page.frameLocator("iframe");
    await expect(frame.locator("html")).toHaveAttribute("data-theme", theme);
    await frame.locator('.reader-toolbar [data-report-view="full"]').click();
    await expect(
      frame.locator('.report-shell[data-lang-body="zh"]'),
    ).toContainText("目标人群");
  }
});
