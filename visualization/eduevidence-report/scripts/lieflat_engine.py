#!/usr/bin/env python3
"""lieflat_engine.py — Data-driven, theme-aware Lieflat Charts pure-SVG renderers.

Every renderer receives a normalized data bundle produced by charts_data.py
(the ONLY numeric source) and emits a themed inline SVG. There is no demo or
hardcoded data anywhere in this module.

Contracts (per the Lieflat Charts codex / mono-tokens.js):
  - No inline <style> blocks: elements carry lf-pop / lf-fade / lf-draw classes
    plus an inline --motion-delay variable; motion/motion.css owns the
    animation definitions (quarticOut-family fast-in fast-stop curves).
  - Stagger: dot matrices 8–15 ms per dot (12 ms), bars 80–130 ms per bar
    (100 ms), capped so large batches stay readable.
  - Card chrome (conclusion title / legend subtitle / caption / uppercase
    source line) lives in the HTML card; the SVG is the figure only.
  - Min SVG font size 6.5 px; in-figure numeric values weight 800;
    area encodings use sqrt.
  - Every number drawn is logged through the audit list with its bundle
    origin path so build_report can verify `lieflat_data_bound`.
"""
from __future__ import annotations

import html
import math
from typing import Any, Dict, List, Optional, Tuple

import charts_data as CD

THEME_PALETTES = {
    "claude": {"bg": "#FAF9F5", "card_bg": "#FFFFFF", "text": "#2A2925", "subtext": "#6A6963", "muted": "#8F8E88", "grid": "#E4E3DC", "border": "#DEDDD6", "primary": "#B8694A", "secondary": "#5E8A6A", "accent": "#C99A4A", "ribbon": "#F0EFEB"},
    "academic": {"bg": "#FFFFFF", "card_bg": "#FAFAFA", "text": "#0F172A", "subtext": "#475569", "muted": "#94A3B8", "grid": "#E2E8F0", "border": "#CBD5E1", "primary": "#0F172A", "secondary": "#2563EB", "accent": "#059669", "ribbon": "#F1F5F9"},
    "datalab": {"bg": "#F8FAFC", "card_bg": "#FFFFFF", "text": "#0F172A", "subtext": "#475569", "muted": "#94A3B8", "grid": "#E2E8F0", "border": "#CBD5E1", "primary": "#0284C7", "secondary": "#10B981", "accent": "#F59E0B", "ribbon": "#F0F9FF"},
    "datalab-dark": {"bg": "#0B0F17", "card_bg": "#111827", "text": "#F8FAFC", "subtext": "#94A3B8", "muted": "#64748B", "grid": "#1E293B", "border": "#334155", "primary": "#38BDF8", "secondary": "#10B981", "accent": "#F59E0B", "ribbon": "#1E293B"},
    "presentation": {"bg": "#140A08", "card_bg": "#1C0D0A", "text": "#FBBF24", "subtext": "#D97706", "muted": "#9A3412", "grid": "#2D120B", "border": "#4A2218", "primary": "#F59E0B", "secondary": "#F24D29", "accent": "#10B981", "ribbon": "#2A140E"},
}

STAGGER_DOT = 12   # ms per dot (token range 8–15)
STAGGER_BAR = 100  # ms per bar (token range 80–130)
MIN_FONT = 6.5


def get_theme(theme: str = "claude") -> Dict[str, str]:
    t = theme.lower().replace("_", "-")
    if "dark" in t:
        return THEME_PALETTES["datalab-dark"]
    if "acad" in t:
        return THEME_PALETTES["academic"]
    if "data" in t:
        return THEME_PALETTES["datalab"]
    if "pres" in t or "judge" in t:
        return THEME_PALETTES["presentation"]
    return THEME_PALETTES.get(t, THEME_PALETTES["claude"])


def esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def _delay(ms: float) -> str:
    return f"style=\"--motion-delay:{max(0, round(ms))}ms\""


def lf_pop(ms: float = 0) -> str:
    return f'class="lf-pop" {_delay(ms)}'


def lf_fade(ms: float = 0) -> str:
    return f'class="lf-fade" {_delay(ms)}'


def lf_draw(ms: float = 0) -> str:
    return f'class="lf-draw" {_delay(ms)}'


def _fmt(v: float, digits: int = 2) -> str:
    return f"{v:.{digits}f}"


class Audit:
    """Collects every displayed number as (origin, value) for the
    lieflat_data_bound integrity gate."""

    def __init__(self, out: Optional[list] = None):
        self.out: list[Tuple[str, Any]] = [] if out is None else out

    def log(self, origin: str, value: Any) -> str:
        self.out.append((origin, value))
        if isinstance(value, float):
            return _fmt(value)
        return str(value)


def _svg_open(p: Dict[str, str], w: int, h: int, aria: str) -> List[str]:
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="100%" height="100%" role="img" aria-label="{esc(aria)}" '
            f'style="background:{p["card_bg"]};">']


# ══════════════════════════════════════════════════════════════════════════
# meta.forest — forest plot (Hedges' g + 95% CI)
# ══════════════════════════════════════════════════════════════════════════

def render_forest_plot(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    studies = bundle.get("studies") or []
    pooled = bundle.get("pooled")
    w, h = 820, 96 + len(studies) * 27 + 66
    span = max((abs(s["g"]) for s in studies), default=0.5)
    for s in studies:
        if s.get("ci_lower") is not None:
            span = max(span, abs(s["ci_lower"]))
        if s.get("ci_upper") is not None:
            span = max(span, abs(s["ci_upper"]))
    span = max(0.5, span * 1.15)
    cx = w / 2
    scale = (w * 0.34) / span
    out = _svg_open(p, w, h, meta.get("title", "forest plot"))
    head_y = 40
    out.append(f'<text x="24" y="{head_y}" font-size="11" font-weight="700" fill="{p["subtext"]}" {lf_fade(0)}>Study</text>')
    out.append(f'<text x="200" y="{head_y}" font-size="11" font-weight="700" fill="{p["subtext"]}" {lf_fade(30)}>Dimension</text>')
    out.append(f'<text x="{cx:.0f}" y="{head_y}" text-anchor="middle" font-size="10" font-weight="700" fill="{p["subtext"]}" {lf_fade(60)}>Hedges&#39; g [95% CI]</text>')
    out.append(f'<text x="{w - 24}" y="{head_y}" text-anchor="end" font-size="10" font-weight="700" fill="{p["subtext"]}" {lf_fade(90)}>Effect [95% CI]</text>')
    out.append(f'<line x1="20" y1="{head_y + 8}" x2="{w - 20}" y2="{head_y + 8}" stroke="{p["border"]}" stroke-width="1" {lf_draw(0)}/>')
    # zero line
    out.append(f'<line x1="{cx:.1f}" y1="{head_y + 8}" x2="{cx:.1f}" y2="{h - 56}" stroke="{p["muted"]}" stroke-dasharray="3,3" stroke-width="1" {lf_fade(120)}/>')
    row_y = head_y + 26
    for i, s in enumerate(studies):
        g = float(s["g"])
        ci_l = s.get("ci_lower")
        ci_u = s.get("ci_upper")
        color = p["secondary"] if g > 0.1 else (p["primary"] if g < -0.1 else p["accent"])
        A.log(f"studies[{i}].g", round(g, 4))
        x_pt = cx + g * scale
        out.append(f'<text x="24" y="{row_y + 4}" font-size="10" font-weight="500" fill="{p["text"]}" {lf_fade(i * STAGGER_BAR + 60)}>{esc(str(s["label"])[:26])}</text>')
        if s.get("n") is not None:
            A.log(f"studies[{i}].n", round(float(s["n"]), 4))
        dim = str(s.get("dimension") or "GENERAL").replace("_", " ").title()[:15]
        out.append(f'<text x="200" y="{row_y + 4}" font-size="9" fill="{p["subtext"]}" {lf_fade(i * STAGGER_BAR + 60)}>{esc(dim)}</text>')
        if ci_l is not None and ci_u is not None:
            A.log(f"studies[{i}].ci_lower", round(float(ci_l), 4))
            A.log(f"studies[{i}].ci_upper", round(float(ci_u), 4))
            xl = cx + float(ci_l) * scale
            xu = cx + float(ci_u) * scale
            out.append(f'<line x1="{xl:.1f}" y1="{row_y}" x2="{xu:.1f}" y2="{row_y}" stroke="{color}" stroke-width="1.5" {lf_draw(i * STAGGER_BAR + 120)}/>')
            out.append(f'<line x1="{xl:.1f}" y1="{row_y - 4}" x2="{xl:.1f}" y2="{row_y + 4}" stroke="{color}" stroke-width="1.5" {lf_fade(i * STAGGER_BAR + 140)}/>')
            out.append(f'<line x1="{xu:.1f}" y1="{row_y - 4}" x2="{xu:.1f}" y2="{row_y + 4}" stroke="{color}" stroke-width="1.5" {lf_fade(i * STAGGER_BAR + 140)}/>')
        out.append(f'<rect x="{x_pt - 3.5:.1f}" y="{row_y - 3.5:.1f}" width="7" height="7" fill="{color}" {lf_pop(i * STAGGER_BAR + 150)}><title>{esc(str(s["label"]))} — g = {g:+.2f}{f", N = {s["n"]:.0f}" if s.get("n") else ""}</title></rect>')
        ci_txt = f'{g:+.2f} [{ci_l:+.2f}, {ci_u:+.2f}]' if ci_l is not None and ci_u is not None else f"{g:+.2f}"
        out.append(f'<text x="{w - 24}" y="{row_y + 4}" text-anchor="end" font-size="10" font-weight="800" fill="{color}" {lf_fade(i * STAGGER_BAR + 200)}>{ci_txt}</text>')
        row_y += 27
    # axis
    axis_y = h - 48
    out.append(f'<line x1="{cx - 0.34 * w:.0f}" y1="{axis_y}" x2="{cx + 0.34 * w:.0f}" y2="{axis_y}" stroke="{p["text"]}" stroke-width="1" {lf_draw(200)}/>')
    for tick in (-1.0, -0.5, 0.0, 0.5, 1.0):
        tx = cx + tick * (w * 0.34)
        out.append(f'<line x1="{tx:.1f}" y1="{axis_y}" x2="{tx:.1f}" y2="{axis_y + 5}" stroke="{p["text"]}" stroke-width="1" {lf_fade(220)}/>')
        out.append(f'<text x="{tx:.1f}" y="{axis_y + 16}" text-anchor="middle" font-size="{MIN_FONT + 1.5}" font-weight="600" fill="{p["subtext"]}" {lf_fade(240)}>{tick:+.1f}</text>')
    if pooled:
        g = float(pooled["g"])
        A.log("pooled.g", round(g, 4))
        dx = cx + g * scale
        out.append(f'<path d="M {dx - 7:.1f} {axis_y} L {dx:.1f} {axis_y - 9} L {dx + 7:.1f} {axis_y} L {dx:.1f} {axis_y + 9} Z" fill="{p["text"]}" {lf_pop(400)}><title>Pooled effect: {g:+.2f}</title></path>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# evidence.ranked_effects — L2 Dot Cascade
# ══════════════════════════════════════════════════════════════════════════

def render_dot_cascade(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    studies = bundle.get("studies") or []
    w, h = 540, 300
    out = _svg_open(p, w, h, meta.get("title", "dot cascade"))
    n = len(studies)
    x_start, x_end, y_base = 64, 516, 236
    x_gap = (x_end - x_start) / max(1, n)
    gmax = max(abs(s["g"]) for s in studies) or 1.0
    scale = 92 / gmax
    for i, s in enumerate(studies):
        g = float(s["g"])
        A.log(f"studies[{i}].g", round(g, 4))
        x = x_start + (i + 0.5) * x_gap
        hgt = max(10, abs(g) * scale)
        color = p["secondary"] if g >= 0 else p["primary"]
        dots = int(hgt / 11)
        for d in range(dots):
            dy = y_base - (d + 1) * 11 if g >= 0 else y_base + (d + 1) * 11
            out.append(f'<circle cx="{x:.1f}" cy="{dy:.1f}" r="1.8" fill="{color}" opacity="0.55" {lf_fade(d * STAGGER_DOT + i * STAGGER_BAR + 40)}/>')
        head_y = y_base - hgt if g >= 0 else y_base + hgt
        title = f'{esc(str(s["label"]))} — g = {g:+.2f}' + (f', N = {s["n"]:.0f}' if s.get("n") is not None else "")
        if s.get("n") is not None:
            A.log(f"studies[{i}].n", round(float(s["n"]), 4))
        out.append(f'<circle cx="{x:.1f}" cy="{head_y:.1f}" r="4.8" fill="{color}" {lf_pop(i * STAGGER_BAR + 120)}><title>{title}</title></circle>')
        badge_y = head_y - 9 if g >= 0 else head_y + 15
        out.append(f'<text x="{x:.1f}" y="{badge_y:.1f}" fill="{p["text"]}" font-size="{MIN_FONT + 1.5}" font-weight="800" text-anchor="middle" {lf_fade(i * STAGGER_BAR + 180)}>{g:+.2f}</text>')
        label = str(s["label"])[:12]
        out.append(f'<text transform="translate({x:.1f},{y_base + 18}) rotate(45)" fill="{p["subtext"]}" font-size="{MIN_FONT + 1.5}" font-weight="600" {lf_fade(i * STAGGER_BAR + 220)}>{esc(label)}</text>')
    out.append(f'<line x1="44" y1="{y_base}" x2="{x_end}" y2="{y_base}" stroke="{p["text"]}" stroke-width="1.2" {lf_draw(150)}/>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# evidence.year_x_dimension — L9 Bubble Almanac
# ══════════════════════════════════════════════════════════════════════════

def render_bubble_almanac(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    years = bundle.get("years") or []
    dims = bundle.get("dimensions") or []
    cells = bundle.get("cells") or []
    w, h = 540, 300
    out = _svg_open(p, w, h, meta.get("title", "bubble almanac"))
    for y in range(70, 262, 7):
        out.append(f'<line x1="44" y1="{y}" x2="520" y2="{y}" stroke="{p["grid"]}" stroke-width="0.5" {lf_fade((y - 70) * 2)}/>')
    x_start, x_gap = 150, (520 - 150) / max(1, len(dims) - 1) if len(dims) > 1 else 0
    if len(dims) == 1:
        x_start = 335
    y_start, y_gap = 92, 44
    for j, d in enumerate(dims):
        x = x_start + j * x_gap
        out.append(f'<text x="{x:.0f}" y="76" fill="{p["text"]}" font-size="9" font-weight="600" text-anchor="middle" {lf_fade(j * STAGGER_BAR + 40)}>{esc(str(d).replace("_", " ")[:14])}</text>')
    for i, y_str in enumerate(years):
        y = y_start + i * y_gap
        out.append(f'<text x="96" y="{y + 4}" fill="{p["subtext"]}" font-size="9" font-weight="800" text-anchor="end" {lf_fade(i * STAGGER_BAR + 80)}>{esc(y_str)}</text>')
    for k, c in enumerate(cells):
        j = dims.index(c["dim"]) if c["dim"] in dims else 0
        i = years.index(c["year"]) if c["year"] in years else 0
        n = int(c["n"])
        A.log(f"cells[{k}].n", n)
        if c.get("sig") is not None:
            A.log(f"cells[{k}].sig", int(c["sig"]))
        bx = x_start + j * x_gap
        by = y_start + i * y_gap
        r = max(3.5, math.sqrt(n) * 3.6)
        color = p["secondary"] if int(c.get("sig") or 0) > 0 else p["primary"]
        out.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r:.1f}" fill="{color}" fill-opacity="0.22" stroke="{color}" stroke-width="1.2" {lf_pop(k * STAGGER_DOT + 100)}>'
                   f'<title>{esc(str(c["dim"]))} ({esc(str(c["year"]))}) — N = {n} studies, significant = {c.get("sig", 0)}</title></circle>')
        if int(c.get("sig") or 0) > 0:
            out.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="3.2" fill="{color}" {lf_pop(k * STAGGER_DOT + 160)}/>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# evidence.grouped_distribution — G15 Jitter Strip
# ══════════════════════════════════════════════════════════════════════════

def render_jitter_strip(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    groups = bundle.get("groups") or []
    w, h = 540, 300
    out = _svg_open(p, w, h, meta.get("title", "jitter strip"))
    vals = [v for g in groups for v in g["values"]]
    lo, hi = min(vals), max(vals)
    pad = max((hi - lo) * 0.08, 0.05)
    lo, hi = lo - pad, hi + pad
    px = lambda v: 148 + (v - lo) / max(hi - lo, 1e-9) * 352
    lane_h = 168 / max(1, len(groups))
    for gi, g in enumerate(groups):
        yc = 86 + gi * lane_h + lane_h / 2
        out.append(f'<line x1="148" y1="{yc:.1f}" x2="500" y2="{yc:.1f}" stroke="{p["border"]}" stroke-width="1" {lf_fade(gi * STAGGER_BAR + 40)}/>')
        out.append(f'<text x="136" y="{yc + 3:.1f}" text-anchor="end" font-size="9" font-weight="600" fill="{p["subtext"]}" {lf_fade(gi * STAGGER_BAR + 60)}>{esc(str(g["label"]).replace("_", " ")[:18])}</text>')
        for i, v in enumerate(g["values"]):
            A.log(f"groups[{gi}].values[{i}]", round(float(v), 4))
            jit = ((i * 37) % 11 - 5) * 0.9
            delay = min(gi * STAGGER_BAR + i * STAGGER_DOT, 1400)
            out.append(f'<circle cx="{px(v):.1f}" cy="{yc + jit:.1f}" r="2.7" fill="{p["primary"] if gi % 2 else p["text"]}" opacity="0.8" {lf_pop(delay)}><title>{esc(str(g["label"]))} — {v:+.2f}</title></circle>')
    for t, tv in ((0, lo), (1, (lo + hi) / 2), (2, hi)):
        tx = px(tv)
        out.append(f'<line x1="{tx:.1f}" y1="260" x2="{tx:.1f}" y2="266" stroke="{p["muted"]}" stroke-width="1" {lf_fade(300)}/>')
        out.append(f'<text x="{tx:.1f}" y="278" text-anchor="middle" font-size="{MIN_FONT + 1.5}" font-weight="600" fill="{p["muted"]}" {lf_fade(320)}>{tv:+.1f}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# evidence.multidim_top — L20 Parallel Coordinates
# ══════════════════════════════════════════════════════════════════════════

def render_parallel_coordinates(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    axes = bundle.get("axes") or []
    rows = bundle.get("rows") or []
    w, h = 720, 300
    out = _svg_open(p, w, h, meta.get("title", "parallel coordinates"))
    top, bot = 78, 252
    n_ax = len(axes)
    xs = [96 + i * (720 - 192) / max(1, n_ax - 1) for i in range(n_ax)]
    if n_ax == 1:
        xs = [408]
    norms: dict[str, tuple] = {}
    for ax in axes:
        key = ax["key"]
        vals = [r[key] for r in rows if r.get(key) is not None]
        lo = min(vals) if vals else 0
        hi = max(vals) if vals else 1
        norms[key] = (lo, hi if hi > lo else lo + 1.0)
    for i, ax in enumerate(axes):
        x = xs[i]
        out.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bot}" stroke="{p["border"]}" stroke-width="1" {lf_fade(i * STAGGER_BAR + 40)}/>')
        out.append(f'<text x="{x:.1f}" y="{top - 12}" text-anchor="middle" font-size="10" font-weight="700" fill="{p["text"]}" {lf_fade(i * STAGGER_BAR + 60)}>{esc(ax.get("label_" + meta.get("lang", "en"), ax.get("label_en", ax["key"])))}</text>')
        lo, hi = norms[ax["key"]]
        out.append(f'<text x="{x:.1f}" y="{bot + 16}" text-anchor="middle" font-size="{MIN_FONT + 1.5}" font-weight="800" fill="{p["subtext"]}" {lf_fade(i * STAGGER_BAR + 80)}>{_fmt(lo, 1)}</text>')
        out.append(f'<text x="{x:.1f}" y="{top - 18}" text-anchor="middle" font-size="{MIN_FONT + 1.5}" font-weight="800" fill="{p["subtext"]}" {lf_fade(i * STAGGER_BAR + 100)}>{_fmt(hi, 1)}</text>')
    for r_i, r in enumerate(rows):
        pts = []
        for i, ax in enumerate(axes):
            v = r.get(ax["key"])
            if v is None:
                pts.append(None)
                continue
            A.log(f"rows[{r_i}].{ax['key']}", round(float(v), 4))
            lo, hi = norms[ax["key"]]
            y = bot - (float(v) - lo) / (hi - lo) * (bot - top)
            pts.append((xs[i], y))
        d_parts = []
        for pt in pts:
            if pt is None:
                continue
            d_parts.append(f"{pt[0]:.1f} {pt[1]:.1f}")
        if len(d_parts) < 2:
            continue
        title = f'{esc(str(r["label"]))} — ' + ", ".join(f'{ax["key"]}={r.get(ax["key"])}' for ax in axes)
        out.append(f'<polyline points="{" ".join(d_parts)}" fill="none" stroke="{p["primary"]}" stroke-width="1" opacity="0.45" {lf_draw(r_i * STAGGER_BAR + 120)}><title>{title}</title></polyline>')
        out.append(f'<circle cx="{d_parts[0].split()[0]}" cy="{d_parts[0].split()[1]}" r="2.4" fill="{p["primary"]}" {lf_pop(r_i * STAGGER_BAR + 140)}/>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# evidence.study_type_composition / wwc — L14 Hundred Field
# ══════════════════════════════════════════════════════════════════════════

def render_hundred_field(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    cats = bundle.get("categories") or []
    w, h = 540, 300
    out = _svg_open(p, w, h, meta.get("title", "hundred field"))
    colors = [p["primary"], p["secondary"], p["accent"], p["muted"]]
    grid_x, grid_y, cell, gap = 40, 74, 15.5, 2.5
    idx = 0
    for c_i, c in enumerate(cats):
        A.log(f"categories[{c_i}].count", int(c["count"]))
        for _ in range(int(c["count"])):
            r, col = divmod(idx, 10)
            if r >= 10:
                break
            x = grid_x + col * (cell + gap)
            y = grid_y + r * (cell + gap)
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3" fill="{colors[c_i % len(colors)]}" {lf_pop(min(idx * STAGGER_DOT, 1100))}><title>{esc(str(c["label"]))} — 1 study</title></rect>')
            idx += 1
    out.append(f'<text x="30" y="270" font-size="8" font-weight="600" fill="{p["muted"]}" {lf_fade(400)}>{esc(meta.get("lang", "en") == "zh" and "每格 = 1 篇研究" or "one cell = one study")}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# evidence.study_type_composition / wwc — F4 Tick Donut
# ══════════════════════════════════════════════════════════════════════════

def render_tick_donut(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    cats = bundle.get("categories") or []
    total = int(bundle.get("total") or 0) or sum(int(c["count"]) for c in cats)
    w, h = 540, 300
    out = _svg_open(p, w, h, meta.get("title", "tick donut"))
    cx, cy, r0, r1 = 200, 158, 88, 104
    colors = [p["primary"], p["secondary"], p["accent"], p["muted"]]
    # largest-remainder share of 100 ticks
    ticks_per = []
    assigned = 0
    for c_i, c in enumerate(cats):
        A.log(f"categories[{c_i}].count", int(c["count"]))
        share = int(c["count"]) / max(total, 1) * 100
        n = int(round(share))
        ticks_per.append((c_i, n))
        assigned += n
    while assigned > 100:  # trim the largest over-assignment
        c_i, n = max(ticks_per, key=lambda t: t[1])
        ticks_per[ticks_per.index((c_i, n))] = (c_i, n - 1)
        assigned -= 1
    while assigned < 100:  # give the remainder to the largest category
        c_i, _ = max(ticks_per, key=lambda t: t[1])
        ticks_per[ticks_per.index((c_i, _))] = (c_i, _ + 1)
        assigned += 1
    tick_i = 0
    for c_i, n in ticks_per:
        for _ in range(n):
            ang = math.radians(-90 + tick_i * 3.6)
            x1, y1 = cx + r0 * math.cos(ang), cy + r0 * math.sin(ang)
            x2, y2 = cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)
            out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{colors[c_i % len(colors)]}" stroke-width="2.4" stroke-linecap="round" {lf_pop(min(tick_i * STAGGER_DOT, 900))}><title>{esc(str(cats[c_i]["label"]))}</title></line>')
            tick_i += 1
    out.append(f'<text x="{cx}" y="{cy - 8}" text-anchor="middle" font-size="22" font-weight="800" fill="{p["text"]}" {lf_pop(500)}>{total}</text>')
    out.append(f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" font-size="9" font-weight="600" fill="{p["subtext"]}" {lf_fade(560)}>{esc(meta.get("lang", "en") == "zh" and "篇研究" or "studies")}</text>')
    out.append(f'<text x="30" y="272" font-size="8" font-weight="600" fill="{p["muted"]}" {lf_fade(600)}>{esc(meta.get("lang", "en") == "zh" and "每 1 tick ≈ 1% 构成" or "one tick ≈ 1% share")}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# outcomes.direction_counts — F5 Tick Rows
# ══════════════════════════════════════════════════════════════════════════

def _dir_colors(p: Dict[str, str]) -> Dict[str, str]:
    return {"positive": p["secondary"], "negative": p["primary"], "null": p["muted"]}


def render_tick_rows(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    rows = sorted(bundle.get("rows") or [], key=lambda r: (r["positive"] - r["negative"]), reverse=True)
    w, h = 540, 300
    out = _svg_open(p, w, h, meta.get("title", "tick rows"))
    colors = _dir_colors(p)
    lane_y = 88
    lane_h = 176 / max(1, len(rows))
    for r_i, r in enumerate(rows):
        yc = lane_y + r_i * lane_h + lane_h / 2
        label = r.get("label_" + meta.get("lang", "en"), r.get("label_en", r["label"]))
        out.append(f'<text x="128" y="{yc + 3:.1f}" text-anchor="end" font-size="9" font-weight="600" fill="{p["subtext"]}" {lf_fade(r_i * STAGGER_BAR + 40)}>{esc(str(label)[:12])}</text>')
        tick = 0
        for key, color in (("positive", colors["positive"]), ("null", colors["null"]), ("negative", colors["negative"])):
            count = int(r.get(key) or 0)
            A.log(f"rows[{r_i}].{key}", count)
            drawn = 0
            for _ in range(count):
                x = 140 + tick * 8
                if x > 496:
                    break
                out.append(f'<circle cx="{x:.1f}" cy="{yc:.1f}" r="2.3" fill="{color}" {lf_pop(min(r_i * STAGGER_BAR + tick * STAGGER_DOT, 1500))}><title>{esc(str(label))} — {key} evidence</title></circle>')
                tick += 1
                drawn += 1
            if drawn < count:
                out.append(f'<text x="{min(140 + tick * 8 + 8, 508)}" y="{yc + 3:.1f}" font-size="{MIN_FONT + 1.5}" font-weight="800" fill="{p["subtext"]}" {lf_fade(r_i * STAGGER_BAR + 400)}>+{count - drawn}</text>')
        out.append(f'<text x="512" y="{yc + 3:.1f}" text-anchor="end" font-size="{MIN_FONT + 1.5}" font-weight="800" fill="{p["text"]}" {lf_fade(r_i * STAGGER_BAR + 500)}>{r["positive"] - r["negative"]:+d}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# outcomes.direction_counts — F1 Rung Bars
# ══════════════════════════════════════════════════════════════════════════

def render_rung_bars(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    rows = bundle.get("rows") or []
    w, h = 540, 300
    out = _svg_open(p, w, h, meta.get("title", "rung bars"))
    colors = _dir_colors(p)
    x_start, x_end, y_base = 60, 516, 240
    bar_w = min(52, (x_end - x_start) / max(1, len(rows)) * 0.62)
    total_max = max((r["positive"] + r["negative"] + r["null"]) for r in rows) or 1
    rung_h = 5.5
    for r_i, r in enumerate(rows):
        cx = x_start + (r_i + 0.5) * (x_end - x_start) / len(rows)
        label = r.get("label_" + meta.get("lang", "en"), r.get("label_en", r["label"]))
        y = y_base
        for key in ("positive", "null", "negative"):
            count = int(r.get(key) or 0)
            A.log(f"rows[{r_i}].{key}", count)
            shown = 0
            for _ in range(count):
                if y_base - y > 118:
                    break
                y -= rung_h + 2.2
                out.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{rung_h}" rx="2.6" fill="{colors[key]}" {lf_fade(r_i * STAGGER_BAR + shown * STAGGER_DOT + 60)}><title>{esc(str(label))} — {key} evidence</title></rect>')
                shown += 1
            if shown < count:
                out.append(f'<text x="{cx:.1f}" y="{y - 4:.1f}" text-anchor="middle" font-size="{MIN_FONT + 1.5}" font-weight="800" fill="{p["subtext"]}" {lf_fade(r_i * STAGGER_BAR + 500)}>+{count - shown}</text>')
        out.append(f'<text x="{cx:.1f}" y="{y_base + 16}" text-anchor="middle" font-size="{MIN_FONT + 1.5}" font-weight="600" fill="{p["subtext"]}" {lf_fade(r_i * STAGGER_BAR + 100)}>{esc(str(label)[:10])}</text>')
        out.append(f'<text x="{cx:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-size="8" font-weight="800" fill="{p["text"]}" {lf_fade(r_i * STAGGER_BAR + 520)}>{r["positive"] + r["negative"] + r["null"]}</text>')
    out.append(f'<line x1="{x_start}" y1="{y_base}" x2="{x_end}" y2="{y_base}" stroke="{p["text"]}" stroke-width="1.2" {lf_draw(120)}/>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# outcomes.paired_counts — F6 Paired Rungs
# ══════════════════════════════════════════════════════════════════════════

def render_paired_rungs(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    rows = bundle.get("rows") or []
    w, h = 540, 300
    out = _svg_open(p, w, h, meta.get("title", "paired rungs"))
    colors = _dir_colors(p)
    group_w = 480 / max(1, len(rows))
    col_w = 13
    y_base = 238
    lang = meta.get("lang", "en")
    out.append(f'<text x="60" y="76" font-size="8" font-weight="700" fill="{colors["positive"]}" {lf_fade(40)}>{esc(lang == "zh" and "正向" or "POSITIVE")}</text>')
    out.append(f'<text x="60" y="92" font-size="8" font-weight="700" fill="{colors["negative"]}" {lf_fade(80)}>{esc(lang == "zh" and "负向" or "NEGATIVE")}</text>')
    for r_i, r in enumerate(rows):
        cx = 60 + (r_i + 0.5) * group_w
        label = r.get("label_" + lang, r.get("label_en", r["label"]))
        for col, key in ((0, "positive"), (1, "negative")):
            count = int(r.get(key) or 0)
            A.log(f"rows[{r_i}].{key}", count)
            shown = 0
            y = y_base
            for _ in range(count):
                if y_base - y > 130:
                    break
                y -= 5.5 + 2.2
                x = cx - col_w - 4 + col * (col_w + 8)
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{col_w}" height="5.5" rx="2.6" fill="{colors[key]}" {lf_fade(r_i * STAGGER_BAR + shown * STAGGER_DOT + 60)}><title>{esc(str(label))} — {key}</title></rect>')
                shown += 1
            if shown < count:
                out.append(f'<text x="{cx:.1f}" y="{y - 4:.1f}" text-anchor="middle" font-size="{MIN_FONT + 1.5}" font-weight="800" fill="{p["subtext"]}" {lf_fade(r_i * STAGGER_BAR + 500)}>+{count - shown}</text>')
        out.append(f'<text x="{cx:.1f}" y="{y_base + 16}" text-anchor="middle" font-size="{MIN_FONT + 1.5}" font-weight="600" fill="{p["subtext"]}" {lf_fade(r_i * STAGGER_BAR + 100)}>{esc(str(label)[:10])}</text>')
        out.append(f'<text x="{cx:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-size="8" font-weight="800" fill="{p["text"]}" {lf_fade(r_i * STAGGER_BAR + 520)}>{r["positive"]} / {r["negative"]}</text>')
    out.append(f'<line x1="46" y1="{y_base}" x2="512" y2="{y_base}" stroke="{p["text"]}" stroke-width="1.2" {lf_draw(120)}/>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# outcomes.bipolar_axes — L7 Brand Spectrum
# ══════════════════════════════════════════════════════════════════════════

def render_brand_spectrum(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    axes = bundle.get("axes") or []
    w, h = 540, 300
    out = _svg_open(p, w, h, meta.get("title", "brand spectrum"))
    lang = meta.get("lang", "en")
    left_t = bundle.get("left_zh" if lang == "zh" else "left_en", "negative")
    right_t = bundle.get("right_zh" if lang == "zh" else "right_en", "positive")
    x0, x1 = 150, 400
    y0, gap = 88, 46
    out.append(f'<text x="{x0 - 12}" y="62" text-anchor="end" font-size="9" font-weight="700" fill="{p["subtext"]}" {lf_fade(40)}>{esc(left_t)}</text>')
    out.append(f'<text x="{x1 + 12}" y="62" font-size="9" font-weight="700" fill="{p["subtext"]}" {lf_fade(80)}>{esc(right_t)}</text>')
    px = lambda t: x0 + t * (x1 - x0)
    ribbon = [f"{px(axes[0]['position']):.1f} {y0}"]
    for i in range(1, len(axes)):
        ribbon.append(f"C {px(axes[i-1]['position']):.1f} {y0 + (i-1)*gap + gap/2:.1f}, {px(axes[i]['position']):.1f} {y0 + i*gap - gap/2:.1f}, {px(axes[i]['position']):.1f} {y0 + i*gap}")
    ribbon_d = f"M {ribbon[0]} " + " ".join(ribbon[1:])
    out.append(f'<path d="{ribbon_d}" fill="none" stroke="{p["ribbon"]}" stroke-width="26" stroke-linecap="round" stroke-linejoin="round" opacity="0.95" {lf_draw(60)}/>')
    for i, ax in enumerate(axes):
        y = y0 + i * gap
        pos = float(ax["position"])
        A.log(f"axes[{i}].position", round(pos, 4))
        A.log(f"axes[{i}].positive", int(ax["positive"]))
        A.log(f"axes[{i}].negative", int(ax["negative"]))
        A.log(f"axes[{i}].null", int(ax["null"]))
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{p["border"]}" stroke-width="1" {lf_fade(i * STAGGER_BAR + 60)}/>')
        out.append(f'<line x1="{x0}" y1="{y - 4}" x2="{x0}" y2="{y + 4}" stroke="{p["border"]}" stroke-width="1" {lf_fade(i * STAGGER_BAR + 60)}/>')
        out.append(f'<line x1="{x1}" y1="{y - 4}" x2="{x1}" y2="{y + 4}" stroke="{p["border"]}" stroke-width="1" {lf_fade(i * STAGGER_BAR + 60)}/>')
        label = ax.get("label_" + lang, ax.get("label_en", ax["label"]))
        out.append(f'<text x="{x0 - 16}" y="{y + 3}" text-anchor="end" font-size="8.5" font-weight="600" fill="{p["subtext"]}" {lf_fade(i * STAGGER_BAR + 90)}>{esc(str(label)[:10])}</text>')
        ux = px(pos)
        net = float(ax["net"])
        A.log(f"axes[{i}].net", round(net, 4))
        net_txt = f"{net * 100:+.0f}%"
        out.append(f'<circle cx="{ux:.1f}" cy="{y}" r="7.5" fill="{p["primary"] if net < 0 else p["secondary"]}" stroke="{p["card_bg"]}" stroke-width="1.8" {lf_pop(i * STAGGER_BAR + 160)}><title>{esc(str(label))} — {esc(left_t)}↔{esc(right_t)}: {net_txt} (pos {ax["positive"]} / neg {ax["negative"]} / null {ax["null"]})</title></circle>')
        out.append(f'<text x="{ux:.1f}" y="{y - 11}" fill="{p["text"]}" font-size="8" font-weight="800" text-anchor="middle" {lf_fade(i * STAGGER_BAR + 220)}>{net_txt}</text>')
    out.append(f'<text x="30" y="278" font-size="8" font-weight="600" fill="{p["muted"]}" {lf_fade(400)}>{esc(bundle.get("derived", ""))[:64]}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# intervention.phase_weeks — L3 Barcode Lollipop
# ══════════════════════════════════════════════════════════════════════════

def render_barcode_lollipop(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    weeks = bundle.get("weeks") or []
    peaks = bundle.get("peaks") or []
    phase_labels = bundle.get("phases") or []
    w, h = 540, 290
    out = _svg_open(p, w, h, meta.get("title", "barcode lollipop"))
    n = len(weeks)
    x_start, x_end = 46, 498
    dx = (x_end - x_start) / max(1, n)
    y_base = 226
    peak_weeks = {pk["week"] for pk in peaks}
    lang = meta.get("lang", "en")
    for i, wk in enumerate(weeks):
        x = x_start + (i + 0.5) * dx
        phase = int(wk["phase"])
        A.log(f"weeks[{i}].week", int(wk["week"]))
        A.log(f"weeks[{i}].phase", phase)
        stem_h = 10 + phase * 16
        y = y_base - stem_h
        out.append(f'<line x1="{x:.1f}" y1="{y_base}" x2="{x:.1f}" y2="{y:.1f}" stroke="{p["grid"]}" stroke-width="0.7" {lf_fade(60)}/>')
        is_peak = wk["week"] in peak_weeks
        out.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{min(y_base, y + 12 + ((i * 7) % 12)):.1f}" stroke="{p["text"]}" stroke-width="{1.4 if is_peak else 0.9}" {lf_fade(min(i * STAGGER_BAR, 1200) + 80)}/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{4.8 if is_peak else 2.5:.1f}" fill="{p["primary"] if is_peak else p["text"]}" {lf_pop(min(i * STAGGER_DOT, 700) + 160)}><title>{esc(lang == "zh" and f"第 {wk['week']} 周 — 阶段 {phase}" or f"week {wk['week']} — phase {phase}")}</title></circle>')
        if is_peak:
            pk = next((q for q in peaks if q["week"] == wk["week"]), None)
            pk_txt = (pk or {}).get("label_zh" if lang == "zh" else "label_en", "")
            out.append(f'<text x="{x:.1f}" y="{y - 9:.1f}" font-size="{MIN_FONT + 1}" font-weight="800" fill="{p["text"]}" text-anchor="middle" {lf_fade(i * STAGGER_BAR + 420)}>{esc(pk_txt)[:12]}</text>')
    for pl in phase_labels:
        i = pl["start"] - bundle.get("first", weeks[0]["week"]) if weeks else 0
        x = x_start + max(0, min(i, n - 1) + 0.5) * dx
        out.append(f'<text x="{x:.1f}" y="248" font-size="8" font-weight="600" fill="{p["muted"]}" {lf_fade(500)}>{esc((pl.get("label_zh" if lang == "zh" else "label_en") or "")[:12])}</text>')
    out.append(f'<line x1="{x_start}" y1="{y_base}" x2="{x_end}" y2="{y_base}" stroke="{p["text"]}" stroke-width="1" {lf_draw(90)}/>')
    out.append(f'<text x="30" y="274" font-size="7.5" font-weight="600" fill="{p["muted"]}" {lf_fade(560)}>{esc(str(bundle.get("derived", ""))[:70])}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# intervention.activity_weights — L1 Launch Fan
# ══════════════════════════════════════════════════════════════════════════

def render_launch_fan(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    items = bundle.get("items") or []
    w, h = 540, 290
    out = _svg_open(p, w, h, meta.get("title", "launch fan"))
    cx, cy, radius = 108, 232, 168
    start_angle, end_angle = -78, 12
    n = len(items)
    d_angle = (end_angle - start_angle) / max(1, n - 1)
    for i, it in enumerate(items):
        wgt = int(it["w"])
        A.log(f"items[{i}].w", wgt)
        ang = math.radians(start_angle + i * d_angle)
        ex, ey = cx + radius * math.cos(ang), cy + radius * math.sin(ang)
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{p["border"]}" stroke-width="1" stroke-dasharray="3,2" {lf_fade(i * STAGGER_BAR + 60)}/>')
        for frac in (0.4, 0.65, 0.85):
            mx, my = cx + radius * frac * math.cos(ang), cy + radius * frac * math.sin(ang)
            out.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="2" fill="{p["muted"]}" opacity="0.55" {lf_fade(i * STAGGER_BAR + 90)}/>')
        r_head = 4.5 + math.sqrt(wgt) * 2.1
        out.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="{r_head:.1f}" fill="{p["secondary"]}" stroke="{p["card_bg"]}" stroke-width="1.5" {lf_pop(i * STAGGER_BAR + 180)}><title>{esc(str(it["label"]))} — {wgt} activities</title></circle>')
        lx, ly = cx + (radius + 22) * math.cos(ang), cy + (radius + 22) * math.sin(ang)
        out.append(f'<text x="{lx:.1f}" y="{ly + 3:.1f}" fill="{p["text"]}" font-size="8.5" font-weight="600" {lf_fade(i * STAGGER_BAR + 240)}>{esc(str(it["label"])[:16])}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# intervention.phase_groups — L8 Dotty Matrix
# ══════════════════════════════════════════════════════════════════════════

def render_dotty_matrix(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    layers = bundle.get("layers") or []
    w, h = 540, 310
    out = _svg_open(p, w, h, meta.get("title", "dotty matrix"))
    shades = [p["text"], p["secondary"], p["accent"], p["muted"]]

    def P(c, r, k):
        return 236 + (c - r) * 17, 244 + (c + r) * 8.4 - k * 52
    for k in range(len(layers)):
        cs = [P(-0.6, -0.6, k), P(5.6, -0.6, k), P(5.6, 5.6, k), P(-0.6, 5.6, k)]
        poly_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in cs) + " Z"
        out.append(f'<path d="{poly_d}" fill="{p["card_bg"]}" fill-opacity="0.96" stroke="{p["border"]}" stroke-width="0.9" {lf_fade(k * STAGGER_BAR + 40)}/>')
        layer = layers[k]
        for ci, cell in enumerate(layer["cells"]):
            A.log(f"layers[{k}].cells[{ci}].r", int(cell["r"]))
            A.log(f"layers[{k}].cells[{ci}].c", int(cell["c"]))
            x, y = P(cell["c"], cell["r"], k)
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.5" fill="{shades[k % len(shades)]}" {lf_pop(min(k * STAGGER_BAR + ci * STAGGER_DOT, 1400))}><title>{esc(str(layer["label"]))} — activity #{ci + 1}</title></circle>')
        cxr, cyr = P(5.6, -0.6, k)
        out.append(f'<line x1="{cxr + 4:.1f}" y1="{cyr:.1f}" x2="{cxr + 20:.1f}" y2="{cyr:.1f}" stroke="{p["muted"]}" stroke-width="0.8" {lf_fade(k * STAGGER_BAR + 200)}/>')
        out.append(f'<text x="{cxr + 24:.1f}" y="{cyr + 2.5:.1f}" font-size="8" font-weight="700" fill="{shades[k % len(shades)]}" {lf_fade(k * STAGGER_BAR + 220)}>{esc(str(layer["label"])[:18])}</text>')
    out.append(f'<text x="30" y="294" font-size="7.5" font-weight="600" fill="{p["muted"]}" {lf_fade(500)}>{esc(str(bundle.get("derived", ""))[:70])}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# decision.confidence_score — F11 Tick Gauge
# ══════════════════════════════════════════════════════════════════════════

def render_tick_gauge(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    score = float(bundle["score"])
    A.log("score", round(score, 4))
    w, h = 540, 290
    out = _svg_open(p, w, h, meta.get("title", "tick gauge"))
    cx, cy, r0, r1 = 240, 158, 92, 108
    filled = int(round(score * 100))
    for i in range(100):
        ang = math.radians(-90 + i * 2.7)
        x1, y1 = cx + r0 * math.cos(ang), cy + r0 * math.sin(ang)
        x2, y2 = cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)
        is_filled = i < filled
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{p["primary"] if is_filled else p["grid"]}" stroke-width="3" stroke-linecap="round" {lf_pop(min(i * STAGGER_DOT, 800)) if is_filled else lf_fade(i * 2 + 60)}><title>{i}%</title></line>')
    out.append(f'<text x="{cx}" y="{cy - 6}" text-anchor="middle" font-size="30" font-weight="800" fill="{p["text"]}" {lf_pop(600)}>{filled}%</text>')
    label = str(bundle.get("label") or "")
    out.append(f'<text x="{cx}" y="{cy + 22}" text-anchor="middle" font-size="10" font-weight="600" fill="{p["subtext"]}" {lf_fade(680)}>{esc(label[:24])}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# methodology.flag_rates — L15 Ballot Tally
# ══════════════════════════════════════════════════════════════════════════

def render_ballot_tally(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    items = bundle.get("items") or []
    w, h = 540, 300
    out = _svg_open(p, w, h, meta.get("title", "ballot tally"))
    lane_y = 92
    lane_h = 176 / max(1, len(items))
    lang = meta.get("lang", "en")
    for r_i, it in enumerate(items):
        total = int(it["total"])
        flagged = int(it["flagged"])
        A.log(f"items[{r_i}].total", total)
        A.log(f"items[{r_i}].flagged", flagged)
        yc = lane_y + r_i * lane_h + lane_h / 2
        label = it.get("label_" + lang, it.get("label_en", it["label"]))
        out.append(f'<text x="150" y="{yc + 3:.1f}" text-anchor="end" font-size="8.5" font-weight="600" fill="{p["subtext"]}" {lf_fade(r_i * STAGGER_BAR + 40)}>{esc(str(label)[:12])}</text>')
        for t in range(total):
            x = 162 + t * 11
            if x > 470:
                break
            out.append(f'<rect x="{x:.1f}" y="{yc - 4:.1f}" width="8" height="8" rx="2" fill="{p["primary"] if t < flagged else p["grid"]}" {lf_pop(min(r_i * STAGGER_BAR + t * STAGGER_DOT, 1400))}><title>{esc(str(label))} — verdict {t + 1}/{total}{" (flagged)" if t < flagged else ""}</title></rect>')
        out.append(f'<text x="512" y="{yc + 3:.1f}" text-anchor="end" font-size="9" font-weight="800" fill="{p["text"]}" {lf_fade(r_i * STAGGER_BAR + 300)}>{flagged}/{total}</text>')
    out.append(f'<text x="30" y="280" font-size="7.5" font-weight="600" fill="{p["muted"]}" {lf_fade(500)}>{esc(str(bundle.get("derived", ""))[:70])}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# evidence.year_x_outcome_counts — L16 Matrix Heat
# ══════════════════════════════════════════════════════════════════════════

def render_matrix_heat(bundle: dict, theme: str, meta: dict, audit: Optional[list] = None) -> str:
    p = get_theme(theme)
    A = Audit(audit)
    years = bundle.get("years") or []
    outcomes = bundle.get("outcomes") or []
    cells = bundle.get("cells") or []
    w = 540
    h = 96 + len(outcomes) * 40 + 24
    out = _svg_open(p, w, h, meta.get("title", "matrix heat"))
    lang = meta.get("lang", "en")
    cell_w = 460 / max(1, len(years))
    cell_h = 32
    x0, y0 = 150, 78
    maxv = max((v for row in cells for v in row), default=1) or 1
    for j, y in enumerate(years):
        x = x0 + (j + 0.5) * cell_w
        out.append(f'<text x="{x:.1f}" y="{y0 - 12}" text-anchor="middle" font-size="9" font-weight="800" fill="{p["subtext"]}" {lf_fade(j * STAGGER_BAR + 40)}>{esc(str(y))}</text>')
    for i, o in enumerate(outcomes):
        label = o.get("label_" + lang, o.get("label_en", o["label"]))
        y = y0 + i * cell_h
        out.append(f'<text x="{x0 - 12}" y="{y + cell_h / 2 + 3:.1f}" text-anchor="end" font-size="8" font-weight="600" fill="{p["subtext"]}" {lf_fade(i * STAGGER_BAR + 60)}>{esc(str(label).replace("_", " ")[:14])}</text>')
        for j in range(len(years)):
            v = int(cells[i][j]) if i < len(cells) and j < len(cells[i]) else 0
            A.log(f"cells[{i}][{j}]", v)
            x = x0 + j * cell_w
            if v > 0:
                opacity = 0.18 + 0.72 * (v / maxv)
                out.append(f'<rect x="{x + 2:.1f}" y="{y + 2:.1f}" width="{cell_w - 4:.1f}" height="{cell_h - 4}" rx="4" fill="{p["primary"]}" fill-opacity="{opacity:.2f}" {lf_pop(min((i + j) * STAGGER_DOT, 900))}/>')
            else:
                out.append(f'<rect x="{x + 2:.1f}" y="{y + 2:.1f}" width="{cell_w - 4:.1f}" height="{cell_h - 4}" rx="4" fill="{p["grid"]}" fill-opacity="0.5" {lf_fade((i + j) * STAGGER_DOT)}/>')
            out.append(f'<text x="{x + cell_w / 2:.1f}" y="{y + cell_h / 2 + 3:.1f}" text-anchor="middle" font-size="{MIN_FONT + 1.5}" font-weight="800" fill="{p["text"]}" {lf_pop(min((i + j) * STAGGER_DOT + 60, 900))}>{v}</text>')
            out.append(f'<title>{esc(str(label))} × {esc(str(years[j]))} — {v} studies</title>')
    out.append("</svg>")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
# Registry + dispatcher
# ══════════════════════════════════════════════════════════════════════════

REGISTRY: Dict[str, Dict[str, Any]] = {
    "forest_plot": {"catalog_ref": "FOREST-PLOT (publication figure)", "source": "meta.forest",
                    "extractor": CD.extract_meta_forest, "renderer": render_forest_plot,
                    "params": {"max_studies": int}},
    "dot_cascade": {"catalog_ref": "L2 Dot Cascade", "source": "evidence.ranked_effects",
                    "extractor": CD.extract_ranked_effects, "renderer": render_dot_cascade,
                    "params": {"limit": int}},
    "bubble_almanac": {"catalog_ref": "L9 Bubble Almanac", "source": "evidence.year_x_dimension",
                       "extractor": CD.extract_year_x_dimension, "renderer": render_bubble_almanac,
                       "params": {}},
    "jitter_strip": {"catalog_ref": "G15 Jitter Strip", "source": "evidence.grouped_distribution",
                     "extractor": CD.extract_grouped_distribution, "renderer": render_jitter_strip,
                     "params": {"limit": int}},
    "parallel_coordinates": {"catalog_ref": "L20 Parallel Coordinates", "source": "evidence.multidim_top",
                             "extractor": CD.extract_multidim_top, "renderer": render_parallel_coordinates,
                             "params": {"limit": int}},
    "hundred_field": {"catalog_ref": "L14 Hundred Field", "source": "evidence.study_type_composition",
                      "extractor": CD.extract_study_type_composition, "renderer": render_hundred_field,
                      "params": {}},
    "tick_donut": {"catalog_ref": "F4 Tick Donut", "source": "evidence.wwc_composition",
                   "extractor": CD.extract_wwc_composition, "renderer": render_tick_donut,
                   "params": {}},
    "tick_rows": {"catalog_ref": "F5 Tick Rows", "source": "outcomes.direction_counts",
                  "extractor": CD.extract_direction_counts, "renderer": render_tick_rows,
                  "params": {"outcomes": list}},
    "rung_bars": {"catalog_ref": "F1 Rung Bars", "source": "outcomes.direction_counts",
                  "extractor": CD.extract_direction_counts, "renderer": render_rung_bars,
                  "params": {"outcomes": list}},
    "paired_rungs": {"catalog_ref": "F6 Paired Rungs", "source": "outcomes.paired_counts",
                     "extractor": CD.extract_paired_counts, "renderer": render_paired_rungs,
                     "params": {"outcomes": list}},
    "brand_spectrum": {"catalog_ref": "L7 Brand Spectrum", "source": "outcomes.bipolar_axes",
                       "extractor": CD.extract_bipolar_axes, "renderer": render_brand_spectrum,
                       "params": {"outcomes": list}},
    "barcode_lollipop": {"catalog_ref": "L3 Barcode Lollipop", "source": "intervention.phase_weeks",
                         "extractor": CD.extract_phase_weeks, "renderer": render_barcode_lollipop,
                         "params": {}},
    "launch_fan": {"catalog_ref": "L1 Launch Fan", "source": "intervention.activity_weights",
                   "extractor": CD.extract_activity_weights, "renderer": render_launch_fan,
                   "params": {"max_items": int}},
    "dotty_matrix": {"catalog_ref": "L8 Dotty Matrix", "source": "intervention.phase_groups",
                     "extractor": CD.extract_phase_groups, "renderer": render_dotty_matrix,
                     "params": {}},
    "tick_gauge": {"catalog_ref": "F11 Tick Gauge", "source": "decision.confidence_score",
                   "extractor": CD.extract_confidence_score, "renderer": render_tick_gauge,
                   "params": {}},
    "ballot_tally": {"catalog_ref": "L15 Ballot Tally", "source": "methodology.flag_rates",
                     "extractor": CD.extract_flag_rates, "renderer": render_ballot_tally,
                     "params": {}},
    "matrix_heat": {"catalog_ref": "L16 Matrix Heat", "source": "evidence.year_x_outcome_counts",
                    "extractor": CD.extract_year_x_outcome_counts, "renderer": render_matrix_heat,
                    "params": {}},
}

LEGACY_TYPES = ("brand_spectrum", "forest_plot", "dot_cascade", "dotty_matrix",
                "barcode_lollipop", "bubble_almanac", "launch_fan")

ACADEMIC_FIGURE_KEYS = ("outcome-comparison.svg", "benchmark-citation-support.svg",
                        "benchmark-quality-cost.svg", "forest-plot.svg")


def render_figure(fig_type: str, bundle: dict, theme: str, meta: dict,
                  audit: Optional[list] = None) -> str:
    """Dispatch to the registered renderer. Unknown types raise ValueError —
    the caller records the reason and never silently falls back."""
    entry = REGISTRY.get(fig_type)
    if entry is None:
        raise ValueError(f"unregistered lieflat chart type: {fig_type!r}")
    return entry["renderer"](bundle, theme, meta or {}, audit)
