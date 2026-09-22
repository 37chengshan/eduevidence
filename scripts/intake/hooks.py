"""Thin orchestrator hooks: prepare run context, finish with optional open."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


from intake.browser import maybe_open_after_run, resolve_main_report
from intake.prompts import is_interactive
from intake.session import run_intake


def prepare_run(
    *,
    question: str,
    depth: str | None = None,
    enhancements: list[str] | None = None,
    domain: str = "education",
    assume_yes: bool = False,
    fallback_depth: str = "M",
) -> dict[str, Any]:
    """Collect intake (or fall back silently). Return orchestrator inputs.

    Keys: question, depth, enhancements, intake_record, wants_mcp, error.
    """
    interactive = (not assume_yes) and is_interactive()
    try:
        record = run_intake(
            question=question,
            depth=depth,
            enhancements=enhancements,
            domain=domain,
            interactive=interactive,
            assume_yes=assume_yes,
        )
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "question": record["research_question"],
        "depth": record["depth"],
        "enhancements": list(record["enhancements"]),
        "intake_record": record,
        "wants_mcp": ("agent_mcp" in record["enhancements"]
                      and "none" not in record["enhancements"]),
        "error": None,
    }


def write_intake_artifact(run_dir: Path | str, intake_record: dict[str, Any] | None) -> None:
    if not intake_record:
        return
    _validate_intake_record(intake_record)
    path = Path(run_dir) / "intake.json"
    path.write_text(json.dumps(intake_record, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _validate_intake_record(record: dict[str, Any]) -> None:
    try:
        import jsonschema
    except ImportError:
        return
    schema_path = (Path(__file__).resolve().parents[2]
                   / "schemas" / "v2" / "intake.schema.json")
    if not schema_path.is_file():
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(record, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(f"intake record failed schema validation: {exc.message}") from exc


def after_run(
    run_dir: Path | str,
    *,
    intake_record: dict[str, Any] | None,
    summary: dict[str, Any],
    printer: Callable[[str], None] = print,
) -> None:
    """Open the main report when the run completed and prefs.open_browser is set."""
    if summary.get("failures") or not summary.get("completed_all"):
        return
    theme = (intake_record or {}).get("default_main_theme")
    if not maybe_open_after_run(run_dir, theme=theme):
        return
    report = resolve_main_report(run_dir, theme)
    if report is not None:
        printer(f"opened report: {report}")
