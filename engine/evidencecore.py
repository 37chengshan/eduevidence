"""engine/evidencecore.py - EvidenceCore v4 domain registry (抽象第一步).

v4 领域包机制：domains/ 注册表 + 领域契约加载 + frame 校验。

- 领域无关常量：DECISION_STATES（四态决策）、PROTOCOL_STEPS（9 步协议）。
- list_domains()：按注册表顺序列出领域。
- load_domain(domain_id)：读取并校验领域条目——所有引用契约必须真实存在。
- validate_frame(domain_id, frame_dict)：用该领域的 frame schema 校验
  frame（education 复用现有 scripts.validate_schema 校验
  schemas/education-frame.schema.json；policy 用 domains/policy/frame.schema.json）。

education 域只是"指向现有契约"的注册：不新增任何逻辑路径、不引入新 schema
或新校验器。领域选择（domain select）由主 agent 接 CLI 完成，引擎层不做选择。

路径解析：当前按仓库布局（domains/ 在仓库根目录）解析；wheel 安装场景的
share/ 回退留给后续步骤（pyproject data-files 未包含 domains/）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_domains_dir() -> Path:
    """Repository layout first; wheel-installed share/ layout as fallback."""
    repo = REPO_ROOT / "domains"
    if repo.is_dir():
        return repo
    import sys
    share = Path(sys.prefix) / "share" / "eduevidence" / "domains"
    if share.is_dir():
        return share
    return repo


DOMAINS_DIR = _resolve_domains_dir()
REGISTRY_FILE = DOMAINS_DIR / "manifest.json"

#: 领域无关：四态决策（README: ADOPT / PILOT / REJECT / INSUFFICIENT EVIDENCE）。
DECISION_STATES = ("adopt", "pilot", "reject", "insufficient_evidence")

#: 领域无关：9 步 EvidenceFlow 协议（SKILL.md Research Core 6 + Decision Extension 3）。
PROTOCOL_STEPS = (
    "Frame", "Retrieve", "Extract", "Challenge", "Audit",
    "Adjudicate", "Applicability", "Intervene", "Evaluate",
)

#: 注册表条目必备字段（domains/manifest.json）。
REQUIRED_REGISTRY_FIELDS = (
    "id", "name", "description", "frame_schema", "outcome_taxonomy",
    "methodology_checklist", "golds_dir", "references_dir",
)

_cache: dict[str, Any] = {}


def _load_registry() -> dict:
    """读取（缓存）domains/manifest.json 注册表。"""
    if "_registry" not in _cache:
        _cache["_registry"] = json.loads(
            REGISTRY_FILE.read_text(encoding="utf-8"))
    return _cache["_registry"]


def list_domains() -> list[dict]:
    """按注册表顺序返回全部领域条目（id/name/description/契约引用）。"""
    return list(_load_registry()["domains"])


def _field_target(entry: dict, field: str) -> Path | None:
    """把注册表路径字段解析为仓库内路径。

    JSON Pointer 引用（"file.json#/pointer"）取文件本体路径；
    指针指向的内容由 _check_pointer 另行校验。None 表示该字段
    明确为 null（可选契约，如 policy 的 golds_dir）。
    """
    raw = entry.get(field)
    if raw is None:
        return None
    return REPO_ROOT / str(raw).partition("#")[0]


def _check_pointer(entry: dict, field: str) -> None:
    """校验 "file.json#/pointer" 引用：文件存在且指针可解析为非空列表。"""
    raw = str(entry[field])
    path_text, _, pointer = raw.partition("#")
    if not pointer:
        return
    target = REPO_ROOT / path_text
    if not target.is_file():
        raise FileNotFoundError(
            f"domain {entry['id']!r}: {field} file missing: {target}")
    node: Any = json.loads(target.read_text(encoding="utf-8"))
    for part in pointer.strip("/").split("/"):
        if not isinstance(node, dict) or part not in node:
            raise ValueError(
                f"domain {entry['id']!r}: {field} pointer {pointer!r} "
                f"unresolvable in {target}")
        node = node[part]
    if not isinstance(node, list) or not node:
        raise ValueError(
            f"domain {entry['id']!r}: {field} pointer {pointer!r} must "
            f"resolve to a non-empty list, got {type(node).__name__}")


def _validate_contracts(entry: dict) -> None:
    """校验领域条目引用的契约真实存在（load_domain 的核心职责）。

    - frame_schema / outcome_taxonomy / methodology_checklist：文件存在且
      为可解析 JSON（指针引用另校验指针内容）；
    - golds_dir / references_dir：目录存在（null 视为"无此契约"，跳过）。
    """
    domain_id = entry["id"]

    def check_file(field: str) -> None:
        target = _field_target(entry, field)
        if target is None:
            raise FileNotFoundError(
                f"domain {domain_id!r}: {field} must reference a file")
        if not target.is_file():
            raise FileNotFoundError(
                f"domain {domain_id!r}: {field} contract missing: {target}")
        json.loads(target.read_text(encoding="utf-8"))  # must parse as JSON
        if "#" in str(entry[field]):
            _check_pointer(entry, field)

    def check_dir(field: str) -> None:
        raw = entry.get(field)
        if raw is None:
            return  # 可选契约（如 policy 的 golds_dir）
        target = REPO_ROOT / str(raw)
        if not target.is_dir():
            raise FileNotFoundError(
                f"domain {domain_id!r}: {field} missing: {target}")

    check_file("frame_schema")
    check_file("outcome_taxonomy")
    check_file("methodology_checklist")
    check_dir("golds_dir")
    check_dir("references_dir")


def load_domain(domain_id: str) -> dict:
    """加载领域条目并校验 manifest/契约存在性。

    Returns: domains/manifest.json 中该领域的注册条目（路径为仓库相对路径）。
    Raises: KeyError（未知领域）；FileNotFoundError / ValueError（契约缺失
    或损坏）。
    """
    for entry in list_domains():
        if entry["id"] == domain_id:
            _validate_contracts(entry)
            return entry
    known = ", ".join(d["id"] for d in list_domains())
    raise KeyError(f"unknown domain {domain_id!r} (registered: {known})")


def validate_frame(domain_id: str, frame: dict) -> list[str]:
    """用该领域的 frame schema 校验 frame dict。

    Returns: 稳定错误字符串列表（空 == 合法），与 engine/contracts.py 的
    validate_record 约定一致；education 复用 scripts.validate_schema 校验
    现有 schemas/education-frame.schema.json，不引入新校验器。
    """
    from scripts.validate_schema import SchemaError, validate  # noqa: PLC0415

    entry = load_domain(domain_id)
    schema_path = _field_target(entry, "frame_schema")
    assert schema_path is not None  # load_domain 已保证存在
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    try:
        validate(frame, schema)
    except SchemaError as exc:
        errors.append(str(exc))
    return errors
