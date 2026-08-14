"""engine/living.py - Living Evidence (v4): subscription, incremental refresh, drift.

A LivingEvidenceSubscription binds a revision-bound DecisionSnapshot to the
project question and a set of query terms. `refresh()` folds newly discovered
evidence into the evidence graph and re-adjudicates:

    * no retrieval layer available  -> a human/agent injects evidence records
      explicitly (`new_evidence=[...]`);
    * a retrieval layer exists      -> a `retriever` adapter callable is
      supplied and returns the same evidence-record shape.

Each refresh commits a new graph revision (GraphMutation: source/study/finding/
evidence_link, optional outcome + methodology audit), runs the tribunal, writes
a fresh immutable DecisionSnapshot, and emits a drift report under living/drift/
comparing the tracked snapshot with the new one via `tribunal.decision_diff`.

Idempotency: evidence records are deduplicated by a canonical content hash
(SHA-256 over the caller-supplied record). Re-injecting the same record never
touches the graph again.

Contracts: schemas/v4/living-subscription.schema.json (subscription record),
schemas/v4/drift-report.schema.json (drift report); graph entities follow
schemas/v2/*.json (source/study/finding/evidence-link/outcome/methodology-audit).
"""
from __future__ import annotations

import hashlib
import json
import secrets
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from engine.contracts import validate_record
from engine.graph_store import GraphMutation, GraphStore
from engine.ids import new_run_id
from engine.project import ProjectWorkspace
from engine.tribunal import adjudicate, decision_diff, save_decision_snapshot
from engine.versions import METHODOLOGY_POLICY_VERSION
from scripts.validate_schema import SchemaError, validate

def _resolve_v4_schema_dir() -> Path:
    """Repository layout first; wheel-installed share/ layout as fallback
    (same pattern as engine/contracts._resolve_schema_dir)."""
    repo = Path(__file__).resolve().parent.parent / "schemas" / "v4"
    if repo.is_dir():
        return repo
    import sys
    share = Path(sys.prefix) / "share" / "eduevidence" / "schemas" / "v4"
    if share.is_dir():
        return share
    return repo


_V4_DIR = _resolve_v4_schema_dir()

#: evidence record key -> (graph table, entity schema name)
_PACKET_TABLES = {
    "source": ("sources", "source"),
    "study": ("studies", "study"),
    "outcome": ("outcomes", "outcome"),
    "finding": ("findings", "finding"),
    "evidence_link": ("evidence_links", "evidence-link"),
    "audit": ("audits", "methodology-audit"),
}

_RELATION_TO_IMPLICATION = {
    "support": "support_adoption",
    "contradict": "oppose_adoption",
    "neutral": "neutral",
}

#: minimum keys a caller-supplied evidence record must carry
_REQUIRED_PACKET_KEYS = ("study", "finding", "evidence_link")

_GRAPH_TABLES = ("sources", "studies", "outcomes", "findings",
                 "evidence_links", "audits")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local_id(prefix: str, existing: set[str]) -> str:
    """Local entity ID (prefix-<8 hex>) without touching engine.ids registry."""
    while True:
        candidate = f"{prefix}-{secrets.token_hex(4)}"
        if candidate not in existing:
            return candidate


def _evidence_hash(packet: dict) -> str:
    """Canonical content hash of a caller-supplied evidence record.

    Independent of dict key order; two identical records always hash equal,
    which is what makes repeat refresh idempotent. Records must be
    JSON-serializable; note that 100 vs 100.0 hash differently (byte-level
    idempotency only, documented in the module docstring).
    """
    canonical = json.dumps(packet, sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_v4(record: dict, schema_name: str) -> None:
    schema_path = _V4_DIR / f"{schema_name}.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        validate(record, schema)
    except SchemaError as exc:
        raise ValueError(f"invalid {schema_name}: {exc}") from exc


# ---- subscription persistence ------------------------------------------

def _subscription_path(project: ProjectWorkspace, subscription_id: str) -> Path:
    return project.path / "living" / "subscriptions" / f"{subscription_id}.json"


def _load_subscription(project: ProjectWorkspace, subscription_id: str) -> dict:
    if not re.fullmatch(r"SUB-[0-9a-f]{8}", str(subscription_id)):
        raise ValueError(
            f"invalid subscription id {subscription_id!r}; expected SUB-<hex8>")
    path = _subscription_path(project, subscription_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"subscription not found: {subscription_id} (missing {path})")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_subscription(project: ProjectWorkspace, subscription: dict) -> Path:
    _validate_v4(subscription, "living-subscription")
    path = _subscription_path(project, subscription["subscription_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(subscription, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return path


def _write_drift_report(project: ProjectWorkspace, drift: dict) -> Path:
    _validate_v4(drift, "drift-report")
    path = project.path / "living" / "drift" / f"{drift['drift_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(drift, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return path


def _tracked_snapshot(project: ProjectWorkspace, subscription: dict) -> dict:
    tracked_id = (subscription.get("extensions") or {}).get("last_snapshot_id") \
        or subscription["decision_snapshot_id"]
    path = project.path / "decisions" / f"{tracked_id}.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"tracked decision snapshot {tracked_id!r} missing for subscription "
            f"{subscription['subscription_id']}")
    return json.loads(path.read_text(encoding="utf-8"))


def _dedupe_terms(query_terms: list[str]) -> list[str]:
    """Trim terms and deduplicate case-insensitively (keep first casing)."""
    seen: set[str] = set()
    terms: list[str] = []
    for term in query_terms:
        key = term.strip().lower()
        if key not in seen:
            seen.add(key)
            terms.append(term.strip())
    return terms


# ---- public API --------------------------------------------------------

def create_subscription(project: ProjectWorkspace, decision_snapshot_id: str,
                        query_terms: list[str]) -> dict:
    """Create a living-evidence subscription bound to a DecisionSnapshot.

    Validates that the snapshot exists under project/decisions/ (snapshots are
    immutable and are the only thing a subscription may bind to), then writes
    project/living/subscriptions/<id>.json. The subscription question is the
    project question; query_terms describe what new evidence to watch for.
    """
    if not decision_snapshot_id.startswith("DEC-"):
        raise ValueError(
            f"decision snapshot id must start with 'DEC-', got {decision_snapshot_id!r}")
    snapshot_path = project.path / "decisions" / f"{decision_snapshot_id}.json"
    if not snapshot_path.is_file():
        raise ValueError(
            f"decision snapshot {decision_snapshot_id} not found in this project; "
            "a subscription must bind to a real adjudication")
    if not query_terms or any(not isinstance(t, str) or not t.strip()
                              for t in query_terms):
        raise ValueError("query_terms must be non-empty strings")

    subs_dir = project.path / "living" / "subscriptions"
    existing = {p.stem for p in subs_dir.glob("SUB-*.json")} if subs_dir.is_dir() else set()
    subscription = {
        "subscription_id": _local_id("SUB", existing),
        "decision_snapshot_id": decision_snapshot_id,
        "question": project.manifest()["question"],
        "query_terms": _dedupe_terms(query_terms),
        "status": "active",
        "created_at": _now_iso(),
        "extensions": {
            "last_snapshot_id": decision_snapshot_id,
            "ingested_evidence_hashes": [],
        },
    }
    _save_subscription(project, subscription)
    return subscription


def set_subscription_status(project: ProjectWorkspace, subscription_id: str,
                            status: str) -> dict:
    """Pause or resume a subscription (status: active | paused)."""
    if status not in ("active", "paused"):
        raise ValueError(f"status must be 'active' or 'paused', got {status!r}")
    subscription = _load_subscription(project, subscription_id)
    subscription["status"] = status
    _save_subscription(project, subscription)
    return subscription


def refresh(project: ProjectWorkspace, subscription_id: str, *,
            new_evidence: list[dict] | None = None,
            retriever: Callable[[dict], list[dict]] | None = None) -> dict:
    """Refresh a subscription: fold new evidence in, re-adjudicate, drift-report.

    Evidence sources (exactly one):
      * `new_evidence` - a list of evidence records injected by a human/agent
        when no retrieval layer exists. Each record is a dict with keys
        `study`, `finding`, `evidence_link` (required) and optional
        `source`, `outcome`, `audit`. Graph entity ids may be omitted and
        are then generated; explicit ids must not collide with the graph.
        `evidence_link.claim_id` must reference an existing graph claim
        (claim-binding rule from the V3 pilot seed pattern).
      * `retriever` - an adapter callable `retriever(subscription) -> list[dict]`
        invoked when a retrieval layer exists; returns the same record shape.

    Returns a dict with the drift report and refresh metadata. Re-injecting an
    already-ingested record (same content hash) never commits a graph change.
    """
    if new_evidence is not None and retriever is not None:
        raise ValueError("provide exactly one of new_evidence / retriever")
    if new_evidence is None and retriever is None:
        raise ValueError("no evidence source: pass new_evidence or a retriever callable")

    subscription = _load_subscription(project, subscription_id)
    if subscription.get("status") != "active":
        raise ValueError(
            f"subscription {subscription_id} is {subscription.get('status', 'unknown')!r}; "
            "resume it before refresh")

    if retriever is not None:
        new_evidence = list(retriever(subscription) or [])

    store = GraphStore(project)
    claims = {c["claim_id"] for c in store.read_table("claims")
              if c.get("status", "active") == "active"}
    if not claims:
        raise ValueError("project graph has no claims; a subscription cannot bind evidence")

    ingested = set((subscription.get("extensions") or {})
                   .get("ingested_evidence_hashes", []))
    fresh_packets: list[tuple[str, dict]] = []
    skipped: list[str] = []
    pending_hashes: set[str] = set()
    seen_in_batch: set[str] = set()
    for packet in new_evidence or []:
        if not isinstance(packet, dict):
            raise ValueError(
                f"evidence record must be a dict, got {type(packet).__name__}")
        h = _evidence_hash(packet)
        if h in ingested or h in seen_in_batch:
            skipped.append(h)
            continue
        seen_in_batch.add(h)
        # Idempotent retry (P1-1): a previous refresh may have committed the
        # record's study/finding into the graph but failed before updating the
        # subscription's hash list. Treat graph-presence as ingested and only
        # restore the hash bookkeeping.
        study_id = (packet.get("study") or {}).get("study_id")
        if study_id and store.get("studies", study_id):
            skipped.append(h)
            pending_hashes.add(h)
            continue
        fresh_packets.append((h, packet))

    if not fresh_packets:
        if pending_hashes:
            _restore_ingested_hashes(project, subscription, pending_hashes)
        return _no_change_refresh(project, subscription, store, skipped)

    # ---- normalize + validate fresh evidence ---------------------------
    next_revision = store.active_revision() + 1
    mutation, new_hashes, finding_ids, summary_parts = _build_mutation(
        project, store, subscription, fresh_packets, claims, next_revision)

    revision = store.commit(
        run_id=new_run_id(),
        reason=f"living evidence refresh: {subscription_id}",
        mutation=mutation)
    store.repair_head_mirror()

    snapshot = adjudicate(store, project=project)
    save_decision_snapshot(project, snapshot)

    previous = _tracked_snapshot(project, subscription)
    diff = decision_diff(previous, snapshot)

    suggested = _suggested_action(diff, committed_new_evidence=True)
    summary = _summarize(suggested, diff, previous, snapshot,
                         summary_parts, skipped)

    drift = {
        "drift_id": _local_id("DRF", _existing_drift_ids(project)),
        "subscription_id": subscription_id,
        "from_revision": previous["graph_revision"],
        "to_revision": revision.revision,
        "generated_at": _now_iso(),
        "new_evidence_ids": sorted(finding_ids),
        "summary": summary,
        "suggested_action": suggested,
        "extensions": {
            "evidence_committed": True,
            "new_evidence_hashes": sorted(new_hashes),
            "skipped_duplicate_hashes": sorted(skipped),
            "diff": diff,
            "from_decision_snapshot_id": previous["decision_snapshot_id"],
            "to_decision_snapshot_id": snapshot["decision_snapshot_id"],
        },
    }
    drift_path = _write_drift_report(project, drift)

    ext = dict(subscription.get("extensions") or {})
    ext["last_refreshed_at"] = drift["generated_at"]
    ext["last_drift_id"] = drift["drift_id"]
    ext["last_snapshot_id"] = snapshot["decision_snapshot_id"]
    ext["from_graph_revision"] = previous["graph_revision"]
    ext["to_graph_revision"] = revision.revision
    ext["ingested_evidence_hashes"] = sorted(ingested | new_hashes)
    subscription["extensions"] = ext
    _save_subscription(project, subscription)

    return {
        "subscription_id": subscription_id,
        "drift": drift,
        "drift_report_path": str(drift_path),
        "graph_revision": revision.revision,
        "suggested_action": suggested,
        "snapshot": snapshot,
        "new_evidence_ids": sorted(finding_ids),
        "evidence_committed": True,
    }


# ---- refresh internals -------------------------------------------------

def _existing_drift_ids(project: ProjectWorkspace) -> set[str]:
    drift_dir = project.path / "living" / "drift"
    if not drift_dir.is_dir():
        return set()
    return {p.stem for p in drift_dir.glob("DRF-*.json")}


def _build_mutation(project, store, subscription, fresh_packets, claims,
                    next_revision) -> tuple[GraphMutation, set[str], set[str], list[str]]:
    """Normalize + validate each fresh record and assemble one GraphMutation."""
    existing = {t: {row[_ID_KEY[t]] for row in store.read_table(t)}
                for t in _GRAPH_TABLES}
    upserts: dict[str, list[dict]] = {t: [] for t in _GRAPH_TABLES}
    new_hashes: set[str] = set()
    finding_ids: set[str] = set()
    summary_parts: list[str] = []

    for idx, (content_hash, packet) in enumerate(fresh_packets, start=1):
        label = f"evidence record #{idx}"
        missing = [k for k in _REQUIRED_PACKET_KEYS if k not in packet]
        if missing:
            raise ValueError(
                f"{label} is missing required keys {missing}; an evidence record "
                "must carry study, finding and evidence_link "
                "(source/outcome/audit optional)")
        if not all(isinstance(packet[k], dict) for k in _REQUIRED_PACKET_KEYS):
            raise ValueError(f"{label}: study/finding/evidence_link must be dicts")

        # --- source (optional; auto project-origin when absent) ----------
        source_upserted = False
        source_pkt = packet.get("source")
        if source_pkt is not None:
            src = dict(source_pkt)
            src_id = src.get("source_id")
            if src_id is None or src_id not in existing["sources"]:
                if src_id is None:
                    src_id = _local_id("SRC", existing["sources"])
                    src["source_id"] = src_id
                existing["sources"].add(src_id)
                source_upserted = True
                upserts["sources"].append(src)
        else:
            src_id = _local_id("SRC", existing["sources"])
            existing["sources"].add(src_id)
            src = {
                "source_id": src_id,
                "origin": "project",
                "source_type": "living-refresh",
                "canonical_locator": f"project:living/{subscription['subscription_id']}",
                "validation_status": "valid",
                "content_hash": None,
                "extensions": {"subscription_id": subscription["subscription_id"]},
            }
            source_upserted = True
            upserts["sources"].append(src)

        # --- outcome (optional; reused when the id already exists) -------
        outcome_upserted = False
        outcome = None
        outcome_pkt = packet.get("outcome")
        finding_pkt = packet["finding"]
        out_id = finding_pkt.get("outcome_id")
        if out_id is None and outcome_pkt is not None:
            out_id = outcome_pkt.get("outcome_id") or (
                f"OUT-{outcome_pkt['name']}" if outcome_pkt.get("name") else None)
        if out_id is None:
            raise ValueError(
                f"{label}: finding.outcome_id is required (or provide an 'outcome' "
                "record with a name/outcome_id)")
        if out_id not in existing["outcomes"]:
            if outcome_pkt is None:
                raise ValueError(
                    f"{label}: outcome {out_id!r} is not in the graph; provide an "
                    "'outcome' record to create it")
            outcome = {
                "outcome_id": out_id,
                "name": outcome_pkt.get("name") or out_id[len("OUT-"):],
                "outcome_type": outcome_pkt.get("outcome_type", "learning"),
                "extensions": outcome_pkt.get("extensions") or {},
            }
            existing["outcomes"].add(out_id)
            outcome_upserted = True
            upserts["outcomes"].append(outcome)

        # --- study --------------------------------------------------------
        study = dict(packet["study"])
        study_id = study.get("study_id")
        if study_id is None:
            study_id = _local_id("STU", existing["studies"])
            study["study_id"] = study_id
        if study_id in existing["studies"]:
            raise ValueError(
                f"{label}: study {study_id!r} already exists in the graph; "
                "living evidence must introduce a new study")
        existing["studies"].add(study_id)
        study.setdefault("source_ids", [src_id])
        if not study["source_ids"]:
            study["source_ids"] = [src_id]
        study.setdefault("identity_status", "resolved")
        study.setdefault("extensions", {})
        upserts["studies"].append(study)

        # --- finding -------------------------------------------------------
        finding = dict(packet["finding"])
        finding_id = finding.get("finding_id")
        if finding_id is None:
            finding_id = _local_id("FND", existing["findings"])
            finding["finding_id"] = finding_id
        if finding_id in existing["findings"]:
            raise ValueError(f"{label}: finding {finding_id!r} already exists in the graph")
        existing["findings"].add(finding_id)
        finding.setdefault("study_id", study_id)
        finding.setdefault("outcome_id", out_id)
        finding.setdefault("source_locator", src["canonical_locator"])
        finding.setdefault("extensions", {})
        upserts["findings"].append(finding)
        finding_ids.add(finding_id)

        # --- evidence link (claim-binding rule) ---------------------------
        link = dict(packet["evidence_link"])
        link_id = link.get("evidence_link_id")
        if link_id is None:
            link_id = _local_id("LNK", existing["evidence_links"])
            link["evidence_link_id"] = link_id
        if link_id in existing["evidence_links"]:
            raise ValueError(
                f"{label}: evidence link {link_id!r} already exists in the graph")
        existing["evidence_links"].add(link_id)
        link.setdefault("finding_id", finding_id)
        claim_id = link.get("claim_id")
        if claim_id not in claims:
            raise ValueError(
                f"{label}: claim {claim_id!r} not found in project graph; "
                "an evidence link must bind to an existing claim "
                "(claim-binding rule)")
        relation = link.get("relation_to_claim")
        if relation not in _RELATION_TO_IMPLICATION:
            raise ValueError(
                f"{label}: relation_to_claim must be one of "
                f"{sorted(_RELATION_TO_IMPLICATION)}, got {relation!r}")
        link.setdefault("decision_implication", _RELATION_TO_IMPLICATION[relation])
        link.setdefault("directness", 2)
        link.setdefault("applicability", {"scope_match": "direct"})
        link.setdefault("reasoning_note",
                        f"living evidence refresh: {subscription['subscription_id']}")
        link["created_in_revision"] = link.get("created_in_revision") or next_revision
        link.setdefault("extensions", {})
        upserts["evidence_links"].append(link)

        # --- optional methodology audit -----------------------------------
        audit_upserted = False
        audit_pkt = packet.get("audit")
        if audit_pkt is not None:
            audit = dict(audit_pkt)
            audit_id = audit.get("audit_id")
            if audit_id is None:
                audit_id = _local_id("AUD", existing["audits"])
                audit["audit_id"] = audit_id
            if audit_id in existing["audits"]:
                raise ValueError(f"{label}: audit {audit_id!r} already exists in the graph")
            existing["audits"].add(audit_id)
            audit.setdefault("study_id", study_id)
            audit.setdefault("policy_version", METHODOLOGY_POLICY_VERSION)
            audit.setdefault("audited_at", _now_iso())
            audit.setdefault("bias_checks", [])
            audit.setdefault("confounders", [])
            audit.setdefault("limitations", [])
            audit.setdefault("extensions", {})
            audit_upserted = True
            upserts["audits"].append(audit)

        # --- schema validation of every entity this record upserts --------
        to_validate: list[tuple[str, dict]] = []
        if source_upserted:
            to_validate.append(("source", src))
        to_validate.append(("study", study))
        if outcome_upserted:
            to_validate.append(("outcome", outcome))
        to_validate.append(("finding", finding))
        to_validate.append(("evidence_link", link))
        if audit_upserted:
            to_validate.append(("audit", audit))
        errors: list[str] = []
        for key, entity in to_validate:
            table, schema_name = _PACKET_TABLES[key]
            for err in validate_record(schema_name, entity):
                errors.append(f"{label} {key}: {err}")
        if errors:
            raise ValueError("invalid living evidence record(s):\n- " +
                             "\n- ".join(errors))

        new_hashes.add(content_hash)
        summary_parts.append(
            f"{label}: study {study_id}, finding {finding_id}, link {link_id} "
            f"(claim {claim_id}, {relation})")

    return GraphMutation(upserts=upserts), new_hashes, finding_ids, summary_parts


_ID_KEY = {
    "sources": "source_id", "studies": "study_id", "outcomes": "outcome_id",
    "findings": "finding_id", "evidence_links": "evidence_link_id",
    "audits": "audit_id",
}


def _suggested_action(diff: dict, *, committed_new_evidence: bool) -> str:
    """suggested_action rules:

    action/confidence change -> 'changed'
    new evidence committed but adjudication unchanged -> 'needs_review'
    otherwise -> 'confirmed'
    """
    if diff.get("action_changed") or diff.get("confidence_changed"):
        return "changed"
    if committed_new_evidence:
        return "needs_review"
    return "confirmed"


def _summarize(suggested: str, diff: dict, previous: dict, snapshot: dict,
               summary_parts: list[str], skipped: list[str]) -> str:
    parts: list[str] = []
    if summary_parts:
        parts.append(f"{len(summary_parts)} new evidence record(s) committed")
    if diff.get("action_changed"):
        parts.append(
            f"decision action changed: {previous.get('decision')} -> "
            f"{snapshot.get('decision')}")
    if diff.get("confidence_changed"):
        parts.append(
            f"confidence label changed: {previous.get('confidence_label')} -> "
            f"{snapshot.get('confidence_label')}")
    if diff.get("changed_claims"):
        parts.append(f"changed claims: {sorted(diff['changed_claims'])}")
    if diff.get("new_key_evidence_links"):
        parts.append(
            f"new key evidence links: {len(diff['new_key_evidence_links'])}")
    if skipped:
        parts.append(f"{len(skipped)} duplicate record(s) skipped (content-hash dedupe)")
    if not parts:
        parts.append("no substantive change")
    return "; ".join(parts)


def _restore_ingested_hashes(project, subscription, hashes: set[str]) -> None:
    """Best-effort state recovery (P1-1): a refresh whose graph commit
    succeeded but whose subscription bookkeeping failed left the hashes
    unrecorded; on retry the records are already in the graph, so we only
    need to restore the hash list."""
    ext = dict(subscription.get("extensions") or {})
    ext["ingested_evidence_hashes"] = sorted(
        set(ext.get("ingested_evidence_hashes", [])) | hashes)
    subscription["extensions"] = ext
    _save_subscription(project, subscription)


def _no_change_refresh(project, subscription, store, skipped) -> dict:
    """Refresh with no new evidence: emit a 'confirmed' drift report only.

    No graph revision is created; from_revision == to_revision.
    """
    previous = _tracked_snapshot(project, subscription)
    diff = decision_diff(previous, previous)
    current_rev = store.active_revision()
    now = _now_iso()

    summary = ("refresh received no new evidence" if not skipped else
               f"refresh received {len(skipped)} evidence record(s), all already "
               "ingested (content-hash dedupe)")
    drift = {
        "drift_id": _local_id("DRF", _existing_drift_ids(project)),
        "subscription_id": subscription["subscription_id"],
        "from_revision": current_rev,
        "to_revision": current_rev,
        "generated_at": now,
        "new_evidence_ids": [],
        "summary": summary + "; no graph change",
        "suggested_action": "confirmed",
        "extensions": {
            "evidence_committed": False,
            "new_evidence_hashes": [],
            "skipped_duplicate_hashes": sorted(skipped),
            "diff": diff,
            "from_decision_snapshot_id": previous["decision_snapshot_id"],
            "to_decision_snapshot_id": previous["decision_snapshot_id"],
        },
    }
    drift_path = _write_drift_report(project, drift)

    ext = dict(subscription.get("extensions") or {})
    ext["last_refreshed_at"] = now
    ext["last_drift_id"] = drift["drift_id"]
    ext["from_graph_revision"] = current_rev
    ext["to_graph_revision"] = current_rev
    subscription["extensions"] = ext
    _save_subscription(project, subscription)

    return {
        "subscription_id": subscription["subscription_id"],
        "drift": drift,
        "drift_report_path": str(drift_path),
        "graph_revision": current_rev,
        "suggested_action": "confirmed",
        "snapshot": None,
        "new_evidence_ids": [],
        "evidence_committed": False,
    }
