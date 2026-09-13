#!/usr/bin/env node
/**
 * EduEvidence — 真实录屏 GIF 生成器 (studio-tour / landing-tour)
 *
 * 录的是真实浏览器渲染的真实页面：Chromium CDP 帧捕获 -> ffmpeg palettegen/paletteuse。
 * 不做任何后处理伪造（不合成 UI、不改页面、不 mock 数据）。
 *
 *   cd studio && node record-tour.mjs                 # 生成两个 GIF
 *   cd studio && node record-tour.mjs --only=studio    # 只录控制台
 *   cd studio && node record-tour.mjs --only=landing   # 只录介绍页
 *
 * 实现要点
 *   - 页面滚动用页面内 requestAnimationFrame 缓动（基于滚动位置，不用 CDP 坐标滚轮，避免触控板惯性带来的回弹）；
 *     鼠标用 page.mouse 真实移动/点击，光标可见。
 *   - 帧捕获优先用 Page.startScreencast（跟随合成器帧）；若 1.2s 内没有帧回来，
 *     自动降级为 Page.captureScreenshot 定时轮询（两条路径都写入同一帧序列）。
 *   - 时间维去重：用 ffmpeg tblend 一次性算出全序列相邻帧差，差值低于阈值的“准静止帧”
 *     合并成上一帧输出（页面静止时字幕/噪点不会白吃体积）；剩余帧按最近历史帧补齐时间轴。
 *   - 体积自适应：按 (上限/实测)^0.5 估算目标宽度再重编，逐轮收敛到 ≤3MB，不浪费整轮编码。
 *   - 介绍页录屏期间会暂停页面自身的背景视频与循环 CSS 动画（仅冻结呈现，不改页面文件）。
 *   - 结束时关闭浏览器、停掉自己拉起的服务端口、删除临时帧目录（--keep-frames 可保留）。
 */
import { chromium } from "playwright";
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import fsp from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url)); // <repo>/studio
const ROOT = path.resolve(HERE, ".."); // <repo>
const WEB_DIR = path.join(ROOT, "web");
const OUT_DIR = path.join(WEB_DIR, "assets");
const RUN_ID = Math.random().toString(36).slice(2, 10);
const MARKER = "--eduevidence-tour=" + RUN_ID;
const FFMPEG_CANDIDATES = ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "ffmpeg"];
const FFPROBE_CANDIDATES = ["/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe", "ffprobe"];

const DEFAULTS = {
  only: "all",
  fps: null, // 每场景默认 fps：控制台 15（UI 动效便宜），介绍页 12（大面积渐变贵）
  width: 1200,
  captureWidth: 1280,
  frameHeight: 720,
  minWidth: 720,
  studioPort: 8791,
  landingPort: 8801,
  maxBytes: 3 * 1024 * 1024,
  minSeconds: 8,
  maxSeconds: 14,
  quality: 88,
  // 单次帧间差超过该值（0-255）就保留该帧；低于阈值视为“视觉等同”，
  // 复用上一帧。用于丢掉亚像素抖动/采集噪声，避免白白吃体积（越大越激进）
  dedupeThreshold: 1.5,
  dedupeSpan: 2,
  keepFrames: false,
  headed: false,
  browserChannel: "chrome",
  outDir: OUT_DIR,
};

const SCENES = {
  studio: {
    name: "studio-tour",
    fps: 15,
    // 控制台是浅色数据界面，文字锐利、几乎没有噪声，无需降噪预处理
    prefilter: "",
    maxWidth: 1200,
  },
  landing: {
    name: "landing-tour",
    fps: 12,
    // 介绍页是大面积渐变 + 视频底 + 细密文字，轻度空域降噪能显著降低 GIF 体积
    prefilter: "hqdn3d=3:2:4:3,",
    maxWidth: 1200,
    // 页面里 5 段背景视频一直在播 + pulse/bounce 两个循环动画，
    // 静止画面也会每帧重绘（约 16KB/帧）。录屏时先冻结视频与循环动画，
    // 让“停住阅读”的段落真的停下来——页面本身、文案、图表都不做任何修改。
    freezeMotion: true,
  },
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseArgs(argv) {
  const opts = { ...DEFAULTS };
  for (const raw of argv) {
    const m = /^--([^=]+)(?:=(.*))?$/.exec(raw);
    if (!m) continue;
    const [, key, value] = m;
    const bool = value === undefined || value === "1" || value === "true";
    switch (key) {
      case "only": opts.only = value || "all"; break;
      case "fps": opts.fps = Number(value); break;
      case "width": opts.width = Number(value); break;
      case "min-width": opts.minWidth = Number(value); break;
      case "capture-width": opts.captureWidth = Number(value); break;
      case "frame-height": opts.frameHeight = Number(value); break;
      case "studio-port": opts.studioPort = Number(value); break;
      case "landing-port": opts.landingPort = Number(value); break;
      case "out-dir": opts.outDir = path.resolve(value); break;
      case "browser": opts.browserChannel = value === "chromium" ? null : value; break;
      case "quality": opts.quality = Number(value); break;
      case "dedupe-threshold": opts.dedupeThreshold = Number(value); break;
      case "dedupe-span": opts.dedupeSpan = Number(value); break;
      case "max-bytes": opts.maxBytes = Number(value); break;
      case "keep-frames": opts.keepFrames = bool; break;
      case "headed": opts.headed = bool; break;
      default: console.warn("[warn] 未知参数 " + raw);
    }
  }
  return opts;
}

function log(msg) {
  process.stdout.write(msg + "\n");
}

function findBinary(candidates, args) {
  for (const candidate of candidates) {
    try {
      execFileSync(candidate, args, { stdio: "ignore" });
      return candidate;
    } catch {
      /* try next */
    }
  }
  return null;
}

async function run(bin, args, { allowFail = false } = {}) {
  return await new Promise((resolve) => {
    const child = spawn(bin, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => (stdout += d));
    child.stderr.on("data", (d) => (stderr += d));
    child.on("error", (err) => resolve({ code: -1, stdout, stderr: String(err) }));
    child.on("close", (code) => {
      if (code !== 0 && !allowFail) {
        console.error("[cmd] " + bin + " " + args.join(" ") + "\n" + stderr.slice(-1200));
      }
      resolve({ code, stdout, stderr });
    });
  });
}

async function probe(url, timeoutMs = 1500) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal, redirect: "follow" });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/** 服务已存在则复用（不杀别人的进程），否则自己拉起并在结束时关闭。 */
async function ensureServer({ label, url, port, cwd, argv }) {
  if (await probe(url)) {
    log("[server] " + label + " 已有实例在 127.0.0.1:" + port + "，直接复用");
    return { reused: true, stop: async () => {} };
  }
  const child = spawn(argv[0], argv.slice(1), { cwd, stdio: "ignore", detached: true });
  child.unref();
  const deadline = Date.now() + 25000;
  while (Date.now() < deadline) {
    if (await probe(url)) {
      log("[server] " + label + " 已启动 127.0.0.1:" + port + " (pid " + child.pid + ")");
      return {
        reused: false,
        stop: async () => {
          try { process.kill(-child.pid, "SIGTERM"); } catch { try { child.kill("SIGTERM"); } catch {} }
        },
      };
    }
    await sleep(400);
  }
  throw new Error(label + " 在 " + port + " 端口启动失败");
}

/* ------------------------------------------------------------------ 帧录制 */

class Recorder {
  constructor({ page, context, workDir, opts }) {
    this.page = page;
    this.context = context;
    this.workDir = workDir;
    this.opts = opts;
    this.frames = [];
    this.writes = Promise.resolve();
    this.mode = null;
    this.t0 = 0;
    this.t1 = 0;
    this.loopTimer = null;
    this.inFlight = false;
  }

  async start() {
    this.t0 = Date.now();
    this.cdp = await this.context.newCDPSession(this.page);
    await this.cdp.send("Page.enable");
    this.cdp.on("Page.screencastFrame", (ev) => {
      const t = Date.now() - this.t0;
      const file = path.join(this.workDir, "src-" + String(this.frames.length).padStart(5, "0") + ".jpg");
      this.frames.push({ t, file });
      this.writes = this.writes
        .then(() => fsp.writeFile(file, Buffer.from(ev.data, "base64")))
        .catch(() => {});
      this.cdp.send("Page.screencastFrameAck", { sessionId: ev.sessionId }).catch(() => {});
    });
    await this.cdp.send("Page.startScreencast", {
      format: "jpeg",
      quality: this.opts.quality,
      maxWidth: this.opts.captureWidth,
      maxHeight: this.opts.frameHeight,
      everyNthFrame: 1,
    });
    await sleep(1200);
    if (this.frames.length === 0) {
      log("[frames] screencast 无帧返回，降级为 captureScreenshot 轮询");
      await this.cdp.send("Page.stopScreencast").catch(() => {});
      this.mode = "loop";
      this.loopTimer = setInterval(() => this.captureOnce(), Math.round(1000 / 15));
    } else {
      this.mode = "screencast";
      log("[frames] screencast 模式已就绪（预热 1.2s 收到 " + this.frames.length + " 帧）");
    }
  }

  async captureOnce() {
    if (this.inFlight) return;
    this.inFlight = true;
    try {
      const shot = await this.cdp.send("Page.captureScreenshot", {
        format: "jpeg",
        quality: this.opts.quality,
        captureBeyondViewport: false,
      });
      const t = Date.now() - this.t0;
      const file = path.join(this.workDir, "src-" + String(this.frames.length).padStart(5, "0") + ".jpg");
      this.frames.push({ t, file });
      await fsp.writeFile(file, Buffer.from(shot.data, "base64"));
    } catch {
      /* 丢帧无妨：合成时用上一帧补齐 */
    } finally {
      this.inFlight = false;
    }
  }

  async stop() {
    this.t1 = Date.now();
    if (this.loopTimer) clearInterval(this.loopTimer);
    if (this.mode === "screencast") await this.cdp.send("Page.stopScreencast").catch(() => {});
    await this.writes;
    await sleep(150);
    await this.writes;
    return this.frames.length;
  }

  durationMs() {
    return Math.max(0, this.t1 - this.t0);
  }
}

/* ------------------------------------------------------------------ 交互原语 */

class Tour {
  constructor(page, rec) {
    this.page = page;
    this.rec = rec;
    this.marks = [];
  }

  sleep(ms) {
    return sleep(ms);
  }

  mark(label) {
    this.marks.push({ label, t: Date.now() - this.rec.t0 });
    log("  · " + label + " @" + ((Date.now() - this.rec.t0) / 1000).toFixed(2) + "s");
  }

  waitFor(selector, timeout = 20000) {
    return this.page.waitForSelector(selector, { timeout });
  }

  async center(selector) {
    const box = await this.page.locator(selector).first().boundingBox();
    if (!box) throw new Error("元素不可见: " + selector);
    return { x: box.x + box.width / 2, y: box.y + box.height / 2, box };
  }

  /** 光标缓动到元素中心（真实鼠标事件，光标可见）。 */
  async cursorTo(selector, ms = 600, { settle = 0 } = {}) {
    const target = await this.center(selector);
    const from = this.lastCursor || { x: this.rec.opts.captureWidth / 2, y: 180 };
    const steps = Math.max(6, Math.round(ms / 40));
    for (let i = 1; i <= steps; i++) {
      const k = i / steps;
      const e = 1 - Math.pow(1 - k, 3);
      const x = from.x + (target.x - from.x) * e;
      const y = from.y + (target.y - from.y) * e;
      await this.page.mouse.move(x, y);
      await sleep(Math.max(0, Math.round(ms / steps) - 4));
    }
    this.lastCursor = { x: target.x, y: target.y };
    if (settle) await sleep(settle);
  }

  /** 元素滚入视野（type A 平滑滚动），光标随内容一起上移，最后停在元素中心。 */
  async revealTo(selector, ms = 1600) {
    const locator = this.page.locator(selector).first();
    await locator.scrollIntoViewIfNeeded({ timeout: 5000 }).catch(() => {});
    await sleep(120);
    await this.cursorTo(selector, ms, { settle: 150 });
  }

  /** 页面内 window 滚动缓动，精确落到绝对位置。 */
  scrollWindowTo(y, ms) {
    return this.page.evaluate(
      ({ target, duration }) =>
        new Promise((resolve) => {
          const el = document.scrollingElement;
          const root = document.documentElement;
          const prev = root.style.scrollBehavior;
          root.style.scrollBehavior = "auto";
          const start = el.scrollTop;
          const t0 = performance.now();
          const step = (now) => {
            const k = Math.min(1, (now - t0) / duration);
            const e = 1 - Math.pow(1 - k, 3);
            el.scrollTop = start + (target - start) * e;
            if (k < 1) requestAnimationFrame(step);
            else {
              root.style.scrollBehavior = prev;
              resolve(el.scrollTop);
            }
          };
          requestAnimationFrame(step);
        }),
      { target: y, duration: ms },
    );
  }

  /** 元素内部（scrollable 容器）滚动缓动。 */
  scrollInnerTo(selector, offset, ms) {
    return this.page.evaluate(
      ({ sel, offset, duration }) =>
        new Promise((resolve) => {
          const el = document.querySelector(sel);
          if (!el) return resolve(null);
          const start = el.scrollTop;
          const target = Math.max(0, start + offset);
          const t0 = performance.now();
          const step = (now) => {
            const k = Math.min(1, (now - t0) / duration);
            const e = 1 - Math.pow(1 - k, 3);
            el.scrollTop = start + (target - start) * e;
            if (k < 1) requestAnimationFrame(step);
            else resolve(el.scrollTop);
          };
          requestAnimationFrame(step);
        }),
      { sel: selector, offset, duration: ms },
    );
  }

  async geometry(selector) {
    return await this.page.evaluate((sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: r.top + window.scrollY, height: r.height, vh: window.innerHeight };
    }, selector);
  }

  /** 阅读感：光标轻微漂移 + 内容极小位移（避免整段静止，视觉上仍是“停住阅读”）。 */
  async reading(ms = 1200, { drift = 42 } = {}) {
    const base = this.lastCursor || { x: 640, y: 360 };
    const samples = Math.max(8, Math.round(ms / 50));
    for (let i = 0; i < samples; i++) {
      const k = i / samples;
      await this.page.mouse.move(base.x + Math.sin(k * Math.PI * 2) * 5, base.y + Math.cos(k * Math.PI * 2) * 4);
      if (i % 2 === 0 && drift) {
        await this.page.evaluate((dy) => {
          document.scrollingElement.scrollTop += dy;
        }, drift / samples);
      }
      await sleep(Math.max(0, Math.round(ms / samples) - 4));
    }
    this.lastCursor = null;
  }

  async click(selector, ms = 700, { settle = 250 } = {}) {
    await this.cursorTo(selector, ms);
    const c = this.center(selector);
    const point = await c;
    await this.page.mouse.click(point.x, point.y);
    this.lastCursor = { x: point.x, y: point.y };
    await sleep(settle);
  }
}

/* ------------------------------------------------------------------ 两个场景 */

const STUDIO_URL = (port) => "http://127.0.0.1:" + port + "/studio/";
const LANDING_URL = (port) => "http://127.0.0.1:" + port + "/landing.html";
const STUDIO_CTA = ".feature-case .button.primary";
const STUDIO_REPORTS_TAB = '.project-tabs a[href$="/reports"]';

async function recordStudio({ page, rec, opts }) {
  const tour = new Tour(page, rec);
  log("[studio] 打开 " + STUDIO_URL(opts.studioPort));
  await page.goto(STUDIO_URL(opts.studioPort), { waitUntil: "networkidle" });
  await sleep(600);
  await page.waitForSelector(STUDIO_CTA, { timeout: 20000 });
  await sleep(600);

  await rec.start();
  await sleep(150);

  tour.mark("首页总览");
  await tour.revealTo(STUDIO_CTA, 800);
  await tour.sleep(100);

  await tour.click(STUDIO_CTA, 450, { settle: 500 });
  await tour.waitFor(".project-tabs", 15000);
  await sleep(300);

  tour.mark("打开旗舰项目");
  await tour.click(STUDIO_REPORTS_TAB, 750, { settle: 420 });
  await tour.waitFor(".theme-gallery .theme-card", 15000);
  tour.mark("报告阅读室");
  await tour.cursorTo(".theme-gallery .theme-card >> nth=1", 520, { settle: 140 });
  await tour.cursorTo(".theme-gallery .theme-card >> nth=3", 480, { settle: 120 });

  await tour.click(".theme-gallery .theme-card >> nth=3", 480, { settle: 500 });
  await page.waitForSelector(".reader iframe", { timeout: 20000 });
  await sleep(500);

  tour.mark("打开五主题报告");
  await tour.revealTo(".reader iframe", 1100);
  tour.mark("报告阅读");
  await tour.reading(900, { drift: 60 });

  tour.mark("主题切换");
  await tour.cursorTo(".theme-gallery .theme-card >> nth=4", 700, { settle: 140 });
  await tour.click(".theme-gallery .theme-card >> nth=4", 380, { settle: 500 });
}

async function recordLanding({ page, rec, opts }) {
  const tour = new Tour(page, rec);
  log("[landing] 打开 " + LANDING_URL(opts.landingPort));
  await page.goto(LANDING_URL(opts.landingPort), { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await sleep(1600);
  if (SCENES.landing.freezeMotion) {
    // 录屏时把背景视频停在当前帧、循环动画暂停：页面内容不变，只是不再“自己动”
    await page.addStyleTag({
      content:
        "*,*::before,*::after{animation-play-state:paused !important;}" +
        "video{animation-play-state:paused !important;}",
    });
    await page.evaluate(() => {
      document.querySelectorAll("video").forEach((v) => {
        try {
          v.pause();
        } catch {
          /* ignore */
        }
      });
    });
    await sleep(300);
  }

  await rec.start();
  await sleep(300);
  await page.mouse.move(opts.captureWidth / 2, 180);
  await sleep(200);

  const geom = await page.evaluate(() => {
    const rect = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: Math.round(r.top + window.scrollY), height: Math.round(r.height) };
    };
    return {
      hero: rect("#hero-section"),
      stack: rect("#stacking-section"),
      accordion: rect("#accordion-section"),
      vh: window.innerHeight,
    };
  });
  if (!geom.hero || !geom.stack || !geom.accordion) throw new Error("landing.html 结构未找到预期 section");

  const heroMax = geom.hero.top + geom.hero.height - geom.vh;
  const stackScrollable = geom.stack.height - geom.vh;
  log(
    "[landing] hero " +
      geom.hero.height +
      "px / stack " +
      geom.stack.height +
      "px / accordion@" +
      geom.accordion.top +
      "px / vh " +
      geom.vh,
  );

  tour.mark("hero");
  await tour.cursorTo("#hero-btn-studio", 750, { settle: 130 });
  await tour.sleep(180);

  tour.mark("9步协议");
  const stackTop = geom.stack.top;
  // hero 的滚动联动缩放是整支 GIF 最贵的一段（整屏重绘约 40KB/帧），
  // 所以只借 hero 的滑出做“过场”，把停留时间留给最便宜、信息量最高的 stack 1~3 层卡片
  await tour.scrollWindowTo(Math.round(heroMax * 0.07), 1300);
  await sleep(120);
  await tour.scrollWindowTo(stackTop + Math.round(stackScrollable * 0.34), 2300);
  await tour.sleep(700);

  tour.mark("5套报告体系");
  await tour.scrollWindowTo(geom.accordion.top - 56, 1400);
  await tour.sleep(240);

  await tour.cursorTo(".accordion-panel >> nth=0", 280, { settle: 420 });
  await tour.cursorTo(".accordion-panel >> nth=4", 280, { settle: 480 });
}

/* ------------------------------------------------------------------ 合成 & 编码 */

/**
 * 用 ffmpeg 的 tblend 一次算出整条序列“相邻两帧平均亮度差”（signalstats.YAVG，0-255）。
 * 低值 = 画面上没有肉眼可见变化，只是亚像素抖动 / 采集噪声。
 * 返回 Map<源帧序号(从 1 开始), 与前一帧的差值>。
 */
async function measureDiffs(frames, ffmpeg, fps) {
  const values = new Map();
  if (frames.length < 2) return values;
  const dir = path.dirname(frames[0].file);
  const seqDir = path.join(dir, "diffseq");
  await fsp.mkdir(seqDir, { recursive: true });
  for (let i = 0; i < frames.length; i++) {
    const dst = path.join(seqDir, "d-" + String(i).padStart(5, "0") + ".jpg");
    try {
      fs.linkSync(frames[i].file, dst);
    } catch {
      await fsp.copyFile(frames[i].file, dst);
    }
  }
  const tmp = path.join(dir, "diffs.txt");
  await fsp.rm(tmp, { force: true }).catch(() => {});
  await run(ffmpeg, [
    "-y", "-v", "info",
    "-framerate", String(fps),
    "-i", path.join(seqDir, "d-%05d.jpg"),
    "-vf", "tblend=all_mode=difference,format=gray,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=" + tmp,
    "-f", "null", "-",
  ], { allowFail: true });
  const text = await fsp.readFile(tmp, "utf8").catch(() => "");
  const list = [...text.matchAll(/YAVG=([0-9.eE+-]+)/g)].map((m) => Number(m[1]));
  // tblend 输出的第 n 帧 = 源第 n 帧与第 n-1 帧的差；所以源第 n 帧的差值放在下标 n-1
  for (let i = 0; i < list.length; i++) values.set(i + 1, list[i]);
  await fsp.rm(seqDir, { recursive: true, force: true }).catch(() => {});
  return values;
}

/**
 * 时间维去重：逐步累计差值，累计到“肉眼可见”的量级才保留一帧。
 * 静态画面（差分只来自抖动/噪声）会被压成一帧，真实动效不受影响。
 */
function pickDistinctFrames(frames, diffs, threshold) {
  if (frames.length < 2) return frames.slice();
  const kept = [frames[0]];
  let drift = 0;
  for (let i = 1; i < frames.length; i++) {
    drift += diffs.get(i) ?? threshold + 1;
    if (drift > threshold) {
      kept.push(frames[i]);
      drift = 0;
    }
  }
  const last = frames[frames.length - 1];
  if (kept[kept.length - 1] !== last) kept.push(last);
  return kept;
}

async function composeFrames(rec, opts, workDir, ffmpeg, fps) {
  const frames = rec.frames.filter((f) => fs.existsSync(f.file));
  if (!frames.length) throw new Error("没有捕获到任何帧");
  const totalMs = rec.durationMs();
  const slots = Math.max(1, Math.round((totalMs / 1000) * fps));
  const seqDir = path.join(workDir, "seq");
  await fsp.mkdir(seqDir, { recursive: true });
  const diffs = await measureDiffs(frames, ffmpeg, fps);
  const kept = pickDistinctFrames(frames, diffs, opts.dedupeThreshold);
  let dropped = 0;
  let cursor = 0;
  for (let k = 0; k < slots; k++) {
    const t = (k * 1000) / fps;
    while (cursor + 1 < kept.length && kept[cursor + 1].t <= t) cursor++;
    if (cursor === 0 && k > 0) dropped++;
    await linkInto(seqDir, k + 1, kept[cursor].file);
  }
  const actualFps = kept.length / (totalMs / 1000);
  log(
    "[frames] 源帧 " +
      frames.length +
      " 张（静态/近静态合并 " +
      (frames.length - kept.length) +
      " 张）→ 输出 " +
      slots +
      " 帧 (" +
      fps +
      "fps, " +
      (totalMs / 1000).toFixed(2) +
      "s, 源实拍约 " +
      actualFps.toFixed(1) +
      "fps)",
  );
  return { seqDir, slots, pattern: path.join(seqDir, "frame-%05d.jpg"), dropped };
}

async function linkInto(seqDir, index, source) {
  const dst = path.join(seqDir, "frame-" + String(index).padStart(5, "0") + ".jpg");
  try {
    fs.linkSync(source, dst);
  } catch {
    await fsp.copyFile(source, dst);
  }
}

async function runEncode({ ffmpeg, pattern, outPath, workDir, fps, prefilter, attempt }) {
  const palette = path.join(workDir, "palette.png");
  const scale = prefilter + "scale=" + attempt.width + ":-2:flags=lanczos";
  const gen = await run(ffmpeg, [
    "-y", "-v", "error",
    "-framerate", String(fps),
    "-i", pattern,
    "-vf", scale + ",palettegen=max_colors=" + attempt.colors + ":stats_mode=" + attempt.stats,
    "-frames:v", "1",
    palette,
  ]);
  if (gen.code !== 0) throw new Error("palettegen 失败");
  const use = await run(ffmpeg, [
    "-y", "-v", "error",
    "-framerate", String(fps),
    "-i", pattern,
    "-i", palette,
    "-lavfi", scale + "[x];[x][1:v]paletteuse=dither=" + attempt.dither + ":diff_mode=rectangle",
    "-loop", "0",
    outPath,
  ]);
  if (use.code !== 0) throw new Error("paletteuse 失败");
  return fsp.stat(outPath);
}

/**
 * 按体积上限自适应搜索编码参数：
 * 首轮确定“宽度 → 体积”的斜率，再按比例一步跳到目标宽度，避免逐档重编码。
 */
async function encodeGif({ ffmpeg, ffprobe, pattern, opts, outPath, workDir, fps, prefilter, maxWidth }) {
  const candidates = (width) => [
    { width, colors: 192, stats: "diff", dither: "none" },
    { width, colors: 144, stats: "diff", dither: "none" },
  ];
  const measure = async (attempt) => {
    const stat = await runEncode({ ffmpeg, pattern, outPath, workDir, fps, prefilter, attempt });
    log(
      "[encode] " +
        attempt.width +
        "px / " +
        attempt.colors +
        " 色 → " +
        (stat.size / 1024 / 1024).toFixed(2) +
        "MB",
    );
    return { stat, attempt };
  };

  let width = Math.min(opts.width, maxWidth || opts.width);
  let best = await measure(candidates(width)[0]);
  if (best.stat.size > opts.maxBytes) {
    // 体积≈像素数：按 (目标/实测)^0.5 缩放宽度（宽度对体积的影响接近平方关系）
    const guess = Math.floor(
      width * Math.sqrt((opts.maxBytes * 0.94) / best.stat.size),
    );
    width = Math.max(opts.minWidth, Math.min(width - 40, Math.round(guess / 20) * 20));
    best = await measure(candidates(width)[0]);
    while (best.stat.size > opts.maxBytes && width > opts.minWidth) {
      width = Math.max(opts.minWidth, width - 60);
      best = await measure(candidates(width)[0]);
    }
  }
  if (best.stat.size > opts.maxBytes) {
    const fallback = await measure(candidates(best.attempt.width)[1]);
    if (fallback.stat.size < best.stat.size) best = fallback;
  }
  const meta = await run(ffprobe, [
    "-v", "error",
    "-show_entries", "format=duration,size:stream=width,height,nb_frames",
    "-of", "json",
    outPath,
  ], { allowFail: true });
  let info = { duration: null, width: null, height: null, frames: null };
  try {
    const parsed = JSON.parse(meta.stdout);
    const stream = (parsed.streams || [])[0] || {};
    info = {
      duration: Number(parsed.format?.duration || 0),
      width: stream.width,
      height: stream.height,
      frames: Number(stream.nb_frames || 0),
    };
  } catch {
    /* ignore */
  }
  const stat = await fsp.stat(outPath);
  return { stat, info, attempt: best.attempt };
}

/* ------------------------------------------------------------------ 主流程 */

async function launchBrowser(opts) {
  const base = {
    headless: !opts.headed,
    args: [
      MARKER,
      "--force-device-scale-factor=1",
      "--hide-scrollbars",
      "--disable-features=CalculateNativeWinOcclusion",
      "--autoplay-policy=no-user-gesture-required",
    ],
  };
  if (opts.browserChannel) {
    try {
      const browser = await chromium.launch({ ...base, channel: opts.browserChannel });
      return { browser, used: opts.browserChannel };
    } catch (err) {
      log("[warn] " + opts.browserChannel + " 启动失败（" + String(err).split("\n")[0] + "），回退到 Playwright Chromium");
    }
  }
  const browser = await chromium.launch(base);
  return { browser, used: "chromium" };
}

async function newPage(browser, opts) {
  const context = await browser.newContext({
    viewport: { width: opts.captureWidth, height: opts.frameHeight },
    deviceScaleFactor: 1,
    locale: "zh-CN",
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => log("[page-error] " + String(e).slice(0, 160)));
  return { context, page };
}

async function recordOne(kind, { browser, opts, workDir, ffmpeg, ffprobe }) {
  const scene = SCENES[kind];
  const name = scene.name;
  const outPath = path.join(opts.outDir, name + ".gif");
  const fps = opts.fps || scene.fps;
  log("\n=== 录制 " + name + " ===");
  const { context, page } = await newPage(browser, opts);
  const initial = kind === "studio" ? { x: 640, y: 300 } : { x: 640, y: 200 };
  await page.mouse.move(initial.x, initial.y);
  const rec = new Recorder({ page, context, workDir, opts });
  let frames = 0;
  try {
    if (kind === "studio") await recordStudio({ page, rec, opts });
    else await recordLanding({ page, rec, opts });
  } finally {
    frames = await rec.stop();
    await context.close().catch(() => {});
  }
  const composed = await composeFrames(rec, opts, workDir, ffmpeg, fps);
  const encoded = await encodeGif({
    ffmpeg,
    ffprobe,
    pattern: composed.pattern,
    opts,
    outPath,
    workDir,
    fps,
    maxWidth: scene.maxWidth,
    prefilter: scene.prefilter,
  });
  return { name, outPath, frames, slots: composed.slots, fps, scene, ...encoded };
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const ffmpeg = findBinary(FFMPEG_CANDIDATES, ["-version"]);
  const ffprobe = findBinary(FFPROBE_CANDIDATES, ["-version"]);
  if (!ffmpeg || !ffprobe) throw new Error("找不到 ffmpeg/ffprobe（尝试 " + FFMPEG_CANDIDATES.join(", ") + "）");
  await fsp.mkdir(opts.outDir, { recursive: true });

  const kinds = opts.only === "all" ? ["studio", "landing"] : [opts.only];
  for (const k of kinds) if (k !== "studio" && k !== "landing") throw new Error("--only 只支持 studio | landing | all");

  const servers = [];
  let browser = null;
  const workDir = await fsp.mkdtemp(path.join(os.tmpdir(), "eduevidence-tour-"));
  if (opts.keepFrames) log("[work] 保留临时帧目录 " + workDir);
  const results = [];
  let failure = null;
  const cleanup = async () => {
    if (browser) await browser.close().catch(() => {});
    for (const s of servers) await s.stop();
    if (!opts.keepFrames) await fsp.rm(workDir, { recursive: true, force: true }).catch(() => {});
  };
  process.on("SIGINT", () => {
    cleanup().finally(() => process.exit(130));
  });

  try {
    if (kinds.includes("studio")) {
      servers.push(
        await ensureServer({
          label: "Research Studio",
          url: STUDIO_URL(opts.studioPort),
          port: opts.studioPort,
          cwd: ROOT,
          argv: [path.join(ROOT, ".venv", "bin", "python"), "scripts/dashboard_server.py", "--host", "127.0.0.1", "--port", String(opts.studioPort)],
        }),
      );
    }
    if (kinds.includes("landing")) {
      servers.push(
        await ensureServer({
          label: "landing 静态站",
          url: LANDING_URL(opts.landingPort),
          port: opts.landingPort,
          cwd: WEB_DIR,
          argv: ["python3", "-m", "http.server", String(opts.landingPort), "--bind", "127.0.0.1"],
        }),
      );
    }

    const launched = await launchBrowser(opts);
    browser = launched.browser;
    log("[browser] " + launched.used + " / viewport " + opts.captureWidth + "x" + opts.frameHeight + " @1x");

    for (const kind of kinds) {
      const sub = path.join(workDir, kind);
      await fsp.mkdir(sub, { recursive: true });
      results.push(await recordOne(kind, { browser, opts, workDir: sub, ffmpeg, ffprobe }));
    }
  } catch (err) {
    failure = err;
  } finally {
    await cleanup();
  }

  const leftover = await run("pgrep", ["-fl", MARKER], { allowFail: true });
  const chromeLeft = leftover.stdout.trim() ? leftover.stdout.trim().split("\n").length : 0;
  log("\n[cleanup] 残留浏览器进程 " + chromeLeft + " 个；临时帧目录已删除（--keep-frames 可保留）");

  if (failure) {
    console.error("[error] " + (failure.stack || failure.message));
    process.exit(1);
  }

  let bad = 0;
  log("\n=== 结果 ===");
  for (const r of results) {
    const size = r.stat.size;
    const mb = (size / 1024 / 1024).toFixed(2);
    const dur = r.info.duration || 0;
    const problems = [];
    if (size > opts.maxBytes) problems.push("超过 " + (opts.maxBytes / 1024 / 1024).toFixed(0) + "MB");
    if ((r.info.width || 0) > opts.width) problems.push("宽度超过 " + opts.width);
    if (dur < opts.minSeconds || dur > opts.maxSeconds) problems.push("时长 " + dur.toFixed(2) + "s 不在 " + opts.minSeconds + "-" + opts.maxSeconds + "s");
    if (problems.length) bad++;
    log(
      "- " + r.outPath + "\n" +
        "  " + size + " bytes (" + mb + "MB) / " + dur.toFixed(2) + "s / " + r.info.width + "x" + r.info.height +
        " / " + r.info.frames + " 帧 @ " + r.fps + "fps / 调色板 " + r.attempt.colors + " 色 / 抖动 " + r.attempt.dither +
        "\n  源帧 " + r.frames + " 张 → 输出 " + r.slots + " 帧" + (problems.length ? "\n  !! " + problems.join("; ") : ""),
    );
  }
  if (bad) {
    console.error("\n[error] " + bad + " 个 GIF 未满足约束");
    process.exit(1);
  }
  log("\n完成。");
}

main().catch((err) => {
  console.error("[fatal] " + (err.stack || err.message));
  process.exit(1);
});
