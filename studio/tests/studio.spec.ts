import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";
const id = "example--ai-coding-assistant-evidence";
const project = (tab = "overview") => `/studio/#/project/${id}/${tab}`;
const themes = [
  "claude",
  "academic",
  "datalab",
  "datalab-dark",
  "presentation",
];
test.beforeEach(async ({ page }) => {
  await page.goto("/studio/");
  await expect(page.locator("main h1")).toBeVisible();
});

test("catalog, palette, bilingual controls, dark mode and read-only HTTP", async ({
  page,
  request,
}) => {
  const methods: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/")) methods.push(r.method());
  });
  await page.getByRole("button", { name: "English", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "From questions to defensible decisions.",
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Toggle appearance", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-appearance", "dark");
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("dialog").getByRole("textbox").fill("C");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const response = await request.post("/api/studio/catalog", { data: {} });
  expect(response.status()).toBe(405);
  expect(methods.every((m) => m === "GET")).toBeTruthy();
});

test("evidence filters and keyboard-close inspector", async ({ page }) => {
  await page.goto(project("evidence"));
  const rows = page.locator(".evidence-table tbody tr");
  await expect(rows.first()).toBeVisible();
  const total = await rows.count();
  await page.locator(".filter-bar input").fill("E-001");
  expect(await rows.count()).toBeLessThanOrEqual(total);
  await page.locator(".evidence-title").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.locator(".evidence-title").first()).toBeFocused();
  await page.locator(".filter-bar input").fill("NOT-A-REAL-FINDING");
  await expect(rows).toHaveCount(0);
});

test("graph selection exposes existing relationships without graph mutation", async ({
  page,
}) => {
  await page.goto(project("graph"));
  await expect(page.locator(".graph-node-index button").first()).toBeVisible();
  await page.locator(".graph-node-index button").first().click();
  await expect(page.locator(".graph-inspector h3")).toBeVisible();
  const label = await page
    .locator(".graph-node-index button")
    .first()
    .innerText();
  await expect(page.locator(".graph-inspector")).toContainText(label);
});

test("real local run, revision ancestry, source lineage and zero CI", async ({
  page,
  request,
}) => {
  const catalog = await (await request.get("/api/studio/catalog")).json();
  const local = catalog.projects.find((p: any) => p.kind === "project");
  expect(local).toBeTruthy();
  await page.goto(`/studio/#/project/${local.id}/activity`);
  await page.locator(".run-row summary").click();
  await expect(page.locator(".run-body")).toContainText("source_validation");
  await page.goto(`/studio/#/project/${local.id}/revisions`);
  await expect(page.locator(".revision-list")).toContainText("Revision 1");
  await page.goto(`/studio/#/project/${local.id}/evidence`);
  await expect(page.locator(".forest-svg")).toBeVisible();
  const detail = await (
    await request.get(`/api/studio/projects/${local.id}`)
  ).json();
  expect(detail.evidence[0].numeric.ci_lower).toBe(0);
  expect(
    detail.graph.edges.some((e: any) => e.relation === "provenance"),
  ).toBeTruthy();
});

test("all five identities, two reading modes, bilingual navigation and offline content", async ({
  page,
}) => {
  await page.goto(project("reports"));
  await expect(page.locator(".theme-card")).toHaveCount(5);
  for (const theme of themes) {
    await page.locator(`.theme-card.theme-${theme}`).click();
    const frame = page.frameLocator("iframe");
    await expect(frame.locator("html")).toHaveAttribute("data-theme", theme);
    await frame.locator('.reader-toolbar [data-report-view="full"]').click();
    await expect(frame.locator("html")).toHaveAttribute(
      "data-report-view",
      "full",
    );
    await frame.locator('.reader-toolbar [data-lang-target="en"]').click();
    await expect(frame.locator("html")).toHaveAttribute("lang", "en");
    await frame.locator('.reader-toolbar [data-report-view="brief"]').click();
    await expect(
      frame.locator('.report-shell[data-lang-body="en"] .brief-navigation'),
    ).toBeVisible();
  }
  const download = page.waitForEvent("download");
  await page
    .locator(".reader-toolbar button")
    .filter({ hasText: /HTML/ })
    .click();
  expect((await download).suggestedFilename()).toMatch(/\.html$/);
});

test("explicit API failure never becomes a successful empty catalog", async ({
  page,
}) => {
  await page.route("**/api/studio/catalog", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"error":"fixture unavailable"}',
    }),
  );
  await page.reload();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("503");
});

test("static subdirectory deployment does not disclose local research", async ({
  page,
}) => {
  const missing: string[] = [];
  page.on("response", (r) => {
    if (r.status() >= 400) missing.push(r.url());
  });
  await page.goto("http://127.0.0.1:8766/dist_gh_pages/studio/");
  await expect(page.locator("main h1")).toBeVisible();
  await expect(page.locator(".connection")).toContainText(
    /\u9759\u6001|Static/,
  );
  await expect(page.locator("main")).not.toContainText(
    "Fixture-only local research",
  );
  await page.goto(
    `http://127.0.0.1:8766/dist_gh_pages/studio/#/project/${id}/reports`,
  );
  await expect(page.frameLocator("iframe").locator("html")).toHaveAttribute(
    "data-theme",
    "claude",
  );
  expect(missing).toEqual([]);
});

for (const width of [320, 390, 768, 1440]) {
  test(`console responsive, keyboard accessible and readable at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const size = await page.evaluate(() => ({
      viewport: innerWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(size.document).toBeLessThanOrEqual(size.viewport + 1);
    if (width <= 680) {
      await page.locator(".mobile-menu").click();
      await expect(page.locator(".sidebar")).toHaveClass(/is-open/);
      await page.keyboard.press("Escape");
    }
    const scan = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      scan.violations.filter(
        (v) => v.impact === "critical" || v.impact === "serious",
      ),
    ).toEqual([]);
    mkdirSync("test-results/screenshots", { recursive: true });
    await page.screenshot({
      path: `test-results/screenshots/studio-${width}.png`,
      fullPage: true,
    });
  });
}
for (const theme of themes) {
  test(`standalone ${theme}: mobile/full/English and accessibility`, async ({
    page,
  }) => {
    await page.goto(`/api/studio/projects/${id}/report?theme=${theme}`);
    for (const width of [320, 390, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      for (const view of ["brief", "full"]) {
        await page
          .locator(`.reader-toolbar [data-report-view="${view}"]`)
          .click();
        const size = await page.evaluate(() => {
          const shell = Array.from(
            document.querySelectorAll<HTMLElement>(".report-shell"),
          ).find((e) => getComputedStyle(e).display !== "none")!;
          return {
            viewport: innerWidth,
            document: document.documentElement.scrollWidth,
            shell: shell.clientWidth,
            content: shell.scrollWidth,
          };
        });
        expect(size.document).toBeLessThanOrEqual(size.viewport + 1);
        expect(size.content).toBeLessThanOrEqual(size.shell + 1);
      }
    }
    await page.locator('.reader-toolbar [data-report-view="brief"]').click();
    const scan = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      scan.violations.filter(
        (v) => v.impact === "critical" || v.impact === "serious",
      ),
    ).toEqual([]);
    mkdirSync("test-results/screenshots", { recursive: true });
    await page.screenshot({
      path: `test-results/screenshots/report-${theme}.png`,
    });
  });
}
