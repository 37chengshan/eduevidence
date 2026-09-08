import { useEffect, useRef } from "react";

type Input = { x: number; y: number; active: boolean; enabled: boolean };
const follow = (dt: number, duration: number) => 1 - Math.exp(-dt / duration);

/** A demand-driven decorative surface. Pointer input never enters React state. */
function useSurface(
  setup: (
    layer: HTMLDivElement,
    host: HTMLElement,
  ) => {
    draw: (input: Input, dt: number) => boolean;
    resize: () => void;
  },
) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const layer = ref.current!;
    const host = layer.parentElement!;
    const surface = setup(layer, host);
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    const fine = matchMedia("(hover: hover) and (pointer: fine)");
    const input: Input = { x: 0, y: 0, active: false, enabled: false };
    let frame = 0;
    let previous = 0;
    function tick(time: number) {
      frame = 0;
      const dt = previous ? Math.min(time - previous, 50) : 16;
      previous = time;
      const unsettled = surface.draw(input, dt);
      if (unsettled && input.enabled && !document.hidden) wake();
      else {
        previous = 0;
        layer.dataset.motion = "idle";
      }
    }
    function wake() {
      if (!frame && !document.hidden) {
        layer.dataset.motion = "running";
        frame = requestAnimationFrame(tick);
      }
    }
    function reset() {
      const bounds = host.getBoundingClientRect();
      input.enabled =
        !reduced.matches &&
        fine.matches &&
        !document.hidden &&
        bounds.right > 0 &&
        bounds.left < innerWidth;
      input.active = false;
      layer.dataset.motionMode = input.enabled ? "interactive" : "static";
      cancelAnimationFrame(frame);
      frame = 0;
      previous = 0;
      surface.resize();
      surface.draw({ ...input, enabled: false }, 16);
      layer.dataset.motion = "idle";
    }
    function move(event: PointerEvent) {
      if (!input.enabled || event.pointerType === "touch") return;
      input.x = event.clientX;
      input.y = event.clientY;
      input.active = true;
      wake();
    }
    function leave() {
      input.active = false;
      wake();
    }
    function out(event: PointerEvent) {
      if (
        event.relatedTarget instanceof HTMLIFrameElement ||
        !event.relatedTarget
      )
        leave();
    }
    const observer = new ResizeObserver(reset);
    observer.observe(host);
    const appearance = new MutationObserver(reset);
    appearance.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-appearance"],
    });
    // Opening/closing the mobile drawer changes its visibility without resizing it.
    const content = new MutationObserver(reset);
    content.observe(host, {
      childList: true,
      characterData: true,
      subtree: true,
    });
    const visibility = new MutationObserver(reset);
    visibility.observe(host, { attributes: true, attributeFilter: ["class"] });
    host.addEventListener("pointermove", move, { passive: true });
    host.addEventListener("pointerleave", leave);
    host.addEventListener("pointerout", out);
    window.addEventListener("blur", leave);
    window.addEventListener("resize", reset);
    document.addEventListener("visibilitychange", reset);
    reduced.addEventListener("change", reset);
    fine.addEventListener("change", reset);
    reset();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      appearance.disconnect();
      content.disconnect();
      visibility.disconnect();
      host.removeEventListener("pointermove", move);
      host.removeEventListener("pointerleave", leave);
      host.removeEventListener("pointerout", out);
      window.removeEventListener("blur", leave);
      window.removeEventListener("resize", reset);
      document.removeEventListener("visibilitychange", reset);
      reduced.removeEventListener("change", reset);
      fine.removeEventListener("change", reset);
    };
  }, [setup]);
  return ref;
}

function isometric(layer: HTMLDivElement, host: HTMLElement) {
  const canvas = layer.querySelector("canvas")!;
  const ctx = canvas.getContext("2d");
  let width = 0,
    height = 0,
    columns = 0,
    rows = 0,
    unit = 0;
  let color = "";
  let paper = [240, 238, 233];
  let lifts: number[] = [],
    velocities: number[] = [];
  let masks: DOMRect[] = [];
  function resize() {
    width = host.clientWidth;
    height = host.clientHeight;
    unit = width / 18;
    columns = 9;
    rows = Math.ceil(height / 22) + 1;
    lifts = Array<number>(rows * columns).fill(0);
    velocities = Array<number>(rows * columns).fill(0);
    const ratio = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx?.setTransform(ratio, 0, 0, ratio, 0, 0);
    color = getComputedStyle(host).getPropertyValue("--ambient-ink").trim();
    paper = (
      getComputedStyle(host).backgroundColor.match(/[\d.]+/g) || [
        "240",
        "238",
        "233",
      ]
    )
      .slice(0, 3)
      .map(Number);
  }
  function textMasks() {
    masks = [];
    for (const element of host.querySelectorAll(
      ".brand, .sidebar-search, .sidebar-bottom",
    )) {
      masks.push(element.getBoundingClientRect());
    }
    // Mask ink, not the full clickable row: remaining negative space stays connected.
    for (const element of host.querySelectorAll(
      ".nav-label, nav a > span, nav a > svg",
    )) {
      const range = document.createRange();
      range.selectNodeContents(element);
      const rect =
        element instanceof SVGElement
          ? element.getBoundingClientRect()
          : range.getBoundingClientRect();
      masks.push(rect);
    }
  }
  function draw(input: Input, dt: number) {
    if (!ctx) return false;
    ctx.clearRect(0, 0, width, height);
    const bounds = host.getBoundingClientRect();
    textMasks();
    const brandBottom =
      host.querySelector(".brand")?.getBoundingClientRect().bottom ??
      bounds.top;
    let unsettled = false;
    const elapsed = Math.min(dt, 40) / 1000;
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < columns; col++) {
        const index = row * columns + col;
        const x = (col + 0.25 + (row % 2) * 0.5) * unit * 2;
        const y = row * 22 + 8;
        const distance = Math.hypot(
          input.x - bounds.left - x,
          input.y - bounds.top - y,
        );
        // Compact, smooth falloff: nearby rows move; distant cubes stay still.
        const interactionRadius = 68;
        const target =
          input.enabled && input.active && distance < interactionRadius
            ? 12 * (1 + Math.cos((Math.PI * distance) / interactionRadius))
            : 0;
        if (!input.enabled) {
          lifts[index] = 0;
          velocities[index] = 0;
        } else {
          // An underdamped spring gives the whole local height field a visible rebound.
          const steps = Math.max(1, Math.ceil(elapsed / 0.008));
          for (let step = 0; step < steps; step++) {
            const delta = elapsed / steps;
            velocities[index] +=
              ((target - lifts[index]) * 190 - velocities[index] * 15) * delta;
            lifts[index] += velocities[index] * delta;
          }
        }
        if (
          Math.abs(target - lifts[index]) > 0.02 ||
          Math.abs(velocities[index]) > 0.03
        )
          unsettled = true;
        else {
          lifts[index] = target;
          velocities[index] = 0;
        }
        const lift = lifts[index],
          top = y - lift;
        const half = unit * 0.78,
          depth = half * 0.5,
          wall = 4 + Math.max(0, lift);
        const fade = Math.max(0.1, Math.min(1, y / 45, (height - y) / 45));
        const energy = Math.min(1.2, Math.max(0, lift) / 24);
        const polygon = (points: number[][], alpha: number) => {
          ctx.beginPath();
          points.forEach(([px, py], i) =>
            i ? ctx.lineTo(px, py) : ctx.moveTo(px, py),
          );
          ctx.closePath();
          const strength = (alpha + energy * 0.1) * fade;
          const ink = color.split(",").map(Number);
          ctx.fillStyle = `rgb(${paper.map((channel, n) => Math.round(channel + (ink[n] - channel) * strength)).join(",")})`;
          ctx.fill();
          ctx.strokeStyle = `rgba(${color},${(0.12 + energy * 0.16) * fade})`;
          ctx.lineWidth = 0.6;
          ctx.stroke();
        };
        polygon(
          [
            [x - half, top],
            [x, top + depth],
            [x, top + depth + wall],
            [x - half, top + wall],
          ],
          0.04,
        );
        polygon(
          [
            [x, top + depth],
            [x + half, top],
            [x + half, top + wall],
            [x, top + depth + wall],
          ],
          0.075,
        );
        polygon(
          [
            [x, top - depth],
            [x + half, top],
            [x, top + depth],
            [x - half, top],
          ],
          0.035,
        );
      }
    }
    ctx.clearRect(0, 0, width, Math.max(0, brandBottom - bounds.top + 4));
    for (const rect of masks) {
      if (rect.width && rect.height)
        ctx.clearRect(
          rect.left - bounds.left - 9,
          rect.top - bounds.top - 9,
          rect.width + 18,
          rect.height + 18,
        );
    }
    return unsettled;
  }
  return { resize, draw };
}

function glow(layer: HTMLDivElement, host: HTMLElement) {
  const orbs = Array.from(layer.children) as HTMLElement[];
  const positions = orbs.map(() => ({ x: 0, y: 0 }));
  const durations = [90, 180, 320];
  let opacity = 0,
    left = 0,
    initialized = false;
  function resize() {
    left = host.getBoundingClientRect().left;
    layer.style.left = `${Math.max(0, left)}px`;
  }
  function draw(input: Input, dt: number) {
    if (!input.enabled) {
      opacity = 0;
      initialized = false;
      layer.style.opacity = "0";
      return false;
    }
    const target = input.active ? 1 : 0;
    // Linear exit reaches complete transparency in 500ms (no endless decay).
    opacity = target
      ? Math.min(1, opacity + dt / 220)
      : Math.max(0, opacity - dt / 500);
    layer.style.opacity = String(opacity);
    if (!opacity && !input.active) {
      initialized = false;
      return false;
    }
    let unsettled = opacity !== target;
    positions.forEach((position, i) => {
      const x = input.x - left,
        y = input.y;
      if (!initialized) {
        position.x = x;
        position.y = y;
      }
      position.x += (x - position.x) * follow(dt, durations[i]);
      position.y += (y - position.y) * follow(dt, durations[i]);
      if (Math.hypot(x - position.x, y - position.y) > 0.1) unsettled = true;
      orbs[i].style.transform =
        `translate3d(${position.x}px,${position.y}px,0)`;
    });
    initialized = true;
    return unsettled;
  }
  return { resize, draw };
}

export function SidebarField() {
  const ref = useSurface(isometric);
  return (
    <div ref={ref} className="ambient-field" aria-hidden="true">
      <canvas />
    </div>
  );
}

export function WorkspaceGlow() {
  const ref = useSurface(glow);
  return (
    <div ref={ref} className="ambient-glow" aria-hidden="true">
      <i />
      <i />
      <i />
    </div>
  );
}
