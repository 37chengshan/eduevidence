#!/usr/bin/env python3
"""report_copy_pack.py — domain copy-pack loader for the report layer.

Loads domains/<id>/copy/*.json and exposes display lookups so build_report.py
stays free of research-voice dictionaries.
Domain: result.meta.domain → frame.extensions.domain (default education).
Unknown domain: neutral fallback + warning; policy packs reject teaching words.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

#: Canonical six pack files (task contract).
COPY_PACK_FILES = (
    "framing_lexicon.json",
    "section_titles.json",
    "module_labels.json",
    "terminology.json",
    "risk_constructs.json",
    "few_shots.json",
)
#: Optional topic-split companions (merged into the canonical view on load).
COMPANION_FILES = (
    "framing_enums.json",
    "module_labels_modules.json",
    "module_labels_nav.json",
    "module_labels_summary.json",
    "module_labels_tables.json",
    "module_labels_footer.json",
    "module_labels_v2.json",
)
NEUTRAL_DOMAIN = "_neutral"
DEFAULT_DOMAIN = "education"

#: Chapter skeleton is structure (not copy); titles/leads come from the pack.
DEFAULT_CHAPTER_SKELETON = (
    {"key": "decision", "modules": ("decision", "scope")},
    {"key": "evidence", "modules": ("retrieval", "outcomes", "evidence")},
    {"key": "quality", "modules": ("quality", "conflicts", "trace")},
    {"key": "action", "modules": ("applicability", "intervention")},
    {"key": "evaluation", "modules": ("evaluation",)},
    {"key": "sources", "modules": ("sources",)},
)
FULL_REPORT_MODULES = (
    "decision", "scope", "retrieval", "outcomes", "evidence", "quality", "conflicts",
    "trace", "applicability", "intervention", "evaluation", "sources",
)

from report_copy_policy_guard import assert_policy_copy_clean  # noqa: E402

_ACTIVE_PACK: dict[str, Any] = {}
_COPY_WARNINGS: list[str] = []

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]

def domains_root() -> Path:
    repo = _repo_root() / "domains"
    if (repo / "manifest.json").is_file():
        return repo
    share = Path(sys.prefix) / "share" / "eduevidence" / "domains"
    return share if (share / "manifest.json").is_file() else repo

def resolve_domain(result: dict) -> tuple[str, list[str]]:
    warnings: list[str] = []
    meta = result.get("meta") or {}
    frame = result.get("research_frame") or {}
    ext = frame.get("extensions") or {}
    domain = str(meta.get("domain") or ext.get("domain") or "").strip().lower()
    if not domain:
        warnings.append(
            "result carries no meta.domain / frame.extensions.domain; "
            f"defaulting to {DEFAULT_DOMAIN}"
        )
        return DEFAULT_DOMAIN, warnings
    return domain, warnings


def load_copy_pack(domain: str, *, strict: bool = False) -> dict[str, Any]:
    warnings: list[str] = []
    root = domains_root() / domain / "copy"
    pack: dict[str, Any] = {"domain": domain, "files": {}, "warnings": warnings}
    if not root.is_dir():
        known = sorted(
            p.parent.parent.name for p in domains_root().glob("*/copy/module_labels.json")
            if p.parent.parent.name != NEUTRAL_DOMAIN
        )
        msg = f"unknown domain {domain!r} (copy packs: {', '.join(known) or 'none'})"
        if strict:
            raise KeyError(msg)
        warnings.append(msg + "; using neutral fallback copy")
        pack["domain"] = NEUTRAL_DOMAIN
        pack["files"] = load_copy_pack(NEUTRAL_DOMAIN, strict=True)["files"]
        return pack
    # optional topic-split companions first (module_labels_*.json, framing_enums.json)
    for extra in sorted(root.glob("*.json")):
        pack["files"][extra.name] = json.loads(extra.read_text(encoding="utf-8"))
    missing = [name for name in COPY_PACK_FILES if name not in pack["files"]]
    if missing:
        msg = f"domain {domain!r} copy pack incomplete: missing {', '.join(missing)}"
        if strict:
            raise FileNotFoundError(msg)
        warnings.append(msg + "; merging neutral fallback for gaps")
        neutral = load_copy_pack(NEUTRAL_DOMAIN, strict=True)["files"]
        for name in missing:
            pack["files"][name] = neutral[name]
    _merge_companions(pack["files"])
    if domain == "policy":
        assert_policy_copy_clean(pack["files"])
    return pack


def _merge_companions(files: dict[str, Any]) -> None:
    """Fold topic-split companions into the canonical six-file view."""
    enums = files.get("framing_enums.json") or {}
    lex = files.setdefault("framing_lexicon.json", {})
    if enums.get("frame_enums"):
        lex["frame_enums"] = enums["frame_enums"]
    base = files.setdefault("module_labels.json", {})
    base_labels = base.setdefault("labels", {})
    for name, payload in list(files.items()):
        if name.startswith("module_labels") and name != "module_labels.json":
            base_labels.update((payload or {}).get("labels") or {})


def activate_copy_pack(result: dict, *, strict: bool = False) -> dict[str, Any]:
    global _ACTIVE_PACK, _COPY_WARNINGS
    domain, warnings = resolve_domain(result)
    pack = load_copy_pack(domain, strict=strict)
    _COPY_WARNINGS = list(warnings) + list(pack.get("warnings") or [])
    for message in _COPY_WARNINGS:
        print(f"WARNING: {message}", file=sys.stderr)
    _ACTIVE_PACK = pack
    return pack

def active_copy_pack() -> dict[str, Any]:
    # Prefer the most recently activated pack; fall back to neutral.
    return _ACTIVE_PACK or load_copy_pack(NEUTRAL_DOMAIN)

def copy_warnings() -> list[str]:
    return list(_COPY_WARNINGS)

def _bilingual(files: dict, file_name: str, *keys, lang: str, default=None):
    node = files.get(file_name) or {}
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
        if node is None:
            return default if default is not None else {}
    if isinstance(node, dict) and ("zh" in node or "en" in node):
        return node.get(lang, default)
    return node if node is not None else default

def build_ui(lang: str, pack: dict | None = None) -> dict:
    from zh_labels import merge_ui

    pack = pack or active_copy_pack()
    files = pack.get("files") or {}
    ui = merge_ui(lang, _bilingual(files, "module_labels.json", "labels", lang=lang, default={}))
    titles = _bilingual(files, "section_titles.json", "section_titles", lang=lang, default={}) or {}
    leads = _bilingual(files, "section_titles.json", "section_leads", lang=lang, default={}) or {}
    if titles:
        ui["section_titles"] = titles
    if leads:
        ui["section_leads"] = leads
    risk = files.get("risk_constructs.json") or {}
    for ui_key, risk_key in (
        ("outcome_separation_title", "separation_title"),
        ("outcome_sep_note", "separation_note"),
        ("method_guard", "method_guard"),
    ):
        value = risk.get(risk_key) or {}
        picked = value.get(lang) if isinstance(value, dict) else value
        if picked:
            ui[ui_key] = picked
    principle = (risk.get("guard_principle") or {}).get(lang)
    if principle:
        ui["guard_principle"] = principle
    return ui

def frame_enum_table(lang: str) -> dict[str, str]:
    files = active_copy_pack().get("files") or {}
    merged = dict(_bilingual(files, "framing_enums.json", "frame_enums", lang=lang, default={}) or {})
    merged.update(_bilingual(files, "framing_lexicon.json", "frame_enums", lang=lang, default={}) or {})
    return merged

def methodology_label_table(lang: str) -> dict[str, str]:
    files = active_copy_pack().get("files") or {}
    return dict(_bilingual(files, "terminology.json", "methodology_labels", lang=lang, default={}) or {})

def scope_field_labels(lang: str) -> dict[str, str]:
    files = active_copy_pack().get("files") or {}
    return dict(_bilingual(files, "framing_lexicon.json", "frame_fields", lang=lang, default={}) or {})

def scope_subfield_labels(lang: str, section: str) -> dict[str, str]:
    files = active_copy_pack().get("files") or {}
    sub = _bilingual(files, "framing_lexicon.json", "frame_subfields", lang=lang, default={}) or {}
    return dict(sub.get(section) or {})

def evidence_detail_label_table(lang: str) -> dict[str, str]:
    files = active_copy_pack().get("files") or {}
    return dict(_bilingual(files, "framing_lexicon.json", "evidence_detail_labels", lang=lang, default={}) or {})

def outcome_group_map() -> dict[str, list[str]]:
    files = active_copy_pack().get("files") or {}
    groups = (files.get("risk_constructs.json") or {}).get("outcome_groups") or {}
    return {key: list(values or []) for key, values in groups.items()}

def default_full_report_plan() -> list[dict[str, Any]]:
    files = active_copy_pack().get("files") or {}
    chapters = (files.get("section_titles.json") or {}).get("default_chapters") or []
    by_key = {str(c.get("key") or ""): c for c in chapters if isinstance(c, dict)}
    plan = []
    for skeleton in DEFAULT_CHAPTER_SKELETON:
        chapter = dict(skeleton)
        source = by_key.get(skeleton["key"]) or {}
        chapter["title_zh"] = source.get("title_zh") or skeleton["key"]
        chapter["title_en"] = source.get("title_en") or skeleton["key"]
        chapter["lead_zh"] = source.get("lead_zh") or ""
        chapter["lead_en"] = source.get("lead_en") or ""
        if source.get("modules"):
            chapter["modules"] = tuple(
                m for m in source["modules"] if m in FULL_REPORT_MODULES
            ) or skeleton["modules"]
        plan.append(chapter)
    return plan

def default_leads(lang: str) -> dict[str, str]:
    key = "lead_zh" if lang == "zh" else "lead_en"
    return {chapter["key"]: chapter.get(key) or "" for chapter in default_full_report_plan()}

def brief_block_titles(lang: str) -> dict[str, tuple[str, str]]:
    files = active_copy_pack().get("files") or {}
    raw = _bilingual(files, "section_titles.json", "brief_blocks", lang=lang, default={}) or {}
    out: dict[str, tuple[str, str]] = {}
    for key, value in raw.items():
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            out[key] = (str(value[0]), str(value[1]))
    return out

# Infographic SVG titles/keywords now resolve through build_infographics(ui=...).
# retitle_infographics remains a thin residual for callers that still render
# with the adapter's built-in education defaults and no ui.
_SVG_TITLE_FIXES = {
    "zh": {
        "教学干预时间线": "intervention",
        "评价设计流程": "evaluation",
    },
    "en": {
        "Intervention Timeline": "intervention",
        "Evaluation Design Flow": "evaluation",
    },
}


def retitle_infographics(infographics: dict, lang: str, ui: dict) -> dict:
    """Replace any leftover education-hardcoded SVG strings with domain copy.

    Prefer build_infographics(..., ui=build_ui(lang)); this residual only
    patches titles/keywords that still carry the built-in education defaults.
    """
    ui_keys = {
        "intervention": ("svg_intervention_title", "Intervention Timeline"),
        "evaluation": ("svg_evaluation_title", "Evaluation Design Flow"),
    }
    measures = list(ui.get("evaluation_measures") or [])
    # EVAL_NODES in build_infographics: baseline/pre, post, retention, transfer.
    node_fixes = {
        "zh": {
            "保持测试": measures[2] if len(measures) > 2 else "持续监测",
            "迁移测试（无 AI）": measures[3] if len(measures) > 3 else "扩展评估",
            "迁移测试": measures[3] if len(measures) > 3 else "扩展评估",
        },
        "en": {
            "retention test": measures[2] if len(measures) > 2 else "Durability",
            "transfer test (no AI)": measures[3] if len(measures) > 3 else "Scale-out",
            "transfer test": measures[3] if len(measures) > 3 else "Scale-out",
        },
    }.get(lang, {})
    out = {}
    for key, svg in (infographics or {}).items():
        text = svg or ""
        for old, slot in _SVG_TITLE_FIXES.get(lang, {}).items():
            if old not in text:
                continue
            ui_key, fallback = ui_keys.get(slot, (None, None))
            replacement = (ui.get(ui_key) if ui_key else None) or fallback or old
            if replacement and replacement != old:
                text = text.replace(old, replacement)
        for old, replacement in node_fixes.items():
            if replacement and replacement != old:
                text = text.replace(old, replacement)
        out[key] = text
    return out
