#!/usr/bin/env python3
"""DOI audit: verify every DOI cited in examples/ against its registry.

R1 of docs/plans/v5.2-v6.0-iteration-plan.md. For every DOI found under
examples/**/*.json(on):

- Crossref hosts most DOIs; arXiv's 10.48550/* lives on DataCite.
- ok        resolves, and (when a local title is paired) titles overlap
            above the threshold
- mismatch  resolves but the registered title looks like a different work
- not_found registry has no such DOI — fabricated or malformed
- error     network / unexpected failure

Writes benchmarks/doi-audit/report.json + report.md (with per-file
provenance) and exits 1 when any not_found/mismatch/error exists unless
--no-fail. Stdlib only.

Security notes: DOIs come from repo files, so requests are pinned to two
allow-listed HTTPS registry hosts, the DOI must match a strict shape check,
and redirects are only followed within those hosts.

Usage:
    python3 scripts/audit_dois.py [--examples-dir examples] [--sleep 0.3]
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[A-Za-z0-9._()/:;-]+)")
_STRICT_DOI_RE = re.compile(r"^10\.\d{4,9}/[A-Za-z0-9._()/:-]+$")
DOI_KEY_RE = re.compile(r"(^|_)(doi)$")
TITLE_KEY_RE = re.compile(r"(^|_)(title)$")
STRIP_SUFFIX = ".,;)"

CROSSREF_API = "https://api.crossref.org/works/{doi}"
DATACITE_API = "https://api.datacite.org/dois/{doi}"
ALLOWED_HOSTS = {"api.crossref.org", "api.datacite.org"}
# arXiv mints DOIs via DataCite, not Crossref — route them accordingly.
DATACITE_PREFIXES = {"10.48550"}
MAILTO = "doi-audit@eduevidence.local"
OVERLAP_THRESHOLD = 0.5


def _clean(doi: str) -> str:
    return doi.rstrip(STRIP_SUFFIX)


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for tok in re.split(r"[^a-z0-9]+", text.lower()):
        if len(tok) > 2:
            out.add(tok)
            if tok.endswith("s") and len(tok) > 3:
                out.add(tok[:-1])  # crude plural fold
    return out


def _overlap(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return None
    return len(ta & tb) / min(len(ta), len(tb))


def walk_records(obj: object) -> dict[str, str | None]:
    """Yield doi -> paired title (or None) for every DOI-bearing dict.

    DOIs appearing bare inside string values are collected too (paired with
    no local title), so prose citations are audited as well.
    """
    found: dict[str, str | None] = {}

    def add(doi: str, title: str | None) -> None:
        if title and not found.get(doi):
            found[doi] = title
        elif doi not in found:
            found[doi] = None

    if isinstance(obj, dict):
        doi_val = None
        title_val = None
        for key, val in obj.items():
            if isinstance(val, str):
                key_l = key.strip().lower()
                if DOI_KEY_RE.search(key_l) and DOI_RE.match(val.strip()):
                    doi_val = _clean(val.strip())
                elif TITLE_KEY_RE.search(key_l) and title_val is None:
                    title_val = val.strip()
                else:
                    for raw in DOI_RE.findall(val):
                        add(_clean(raw), None)
            elif isinstance(val, list) and TITLE_KEY_RE.search(key.strip().lower()):
                # Crossref-style [[ "Title" ]] containers
                for item in val:
                    if isinstance(item, str) and title_val is None:
                        title_val = item
                        break
        if doi_val:
            add(doi_val, title_val)
        for val in obj.values():
            for sub_doi, sub_title in walk_records(val).items():
                add(sub_doi, sub_title)
    elif isinstance(obj, list):
        for item in obj:
            found.update(walk_records(item))
    return found


def collect(records_dir: Path) -> tuple[dict[str, dict], int]:
    """Return doi -> {"titles": Counter-like, "files": [..]} plus occurrences."""
    paired: dict[str, dict] = {}

    def add(doi: str, title: str | None, rel: str) -> None:
        entry = paired.setdefault(doi, {"titles": {}, "files": []})
        if title:
            entry["titles"][title] = entry["titles"].get(title, 0) + 1
        if rel not in entry["files"]:
            entry["files"].append(rel)

    occurrences = 0
    for path in sorted(records_dir.rglob("*")):
        if path.suffix not in {".json", ".jsonl"} or not path.is_file():
            continue
        rel = str(path.relative_to(records_dir.parent))
        try:
            if path.suffix == ".jsonl":
                docs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                docs = [json.loads(path.read_text(encoding="utf-8"))]
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"WARN: skip unparseable {rel}: {exc}", file=sys.stderr)
            continue
        for doc in docs:
            recs = walk_records(doc)
            occurrences += len(recs)
            for doi, title in recs.items():
                add(doi, title, rel)
    return paired, occurrences


class _SameHostRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Only follow redirects that stay on the allow-listed registry hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).hostname not in ALLOWED_HOSTS:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class RegistryClient:
    def __init__(self, sleep_s: float) -> None:
        self.sleep_s = sleep_s
        self.cache: dict[str, tuple[str, dict | None]] = {}
        self.opener = urllib.request.build_opener(_SameHostRedirectHandler)

    def fetch(self, doi: str) -> tuple[str, dict | None]:
        if doi in self.cache:
            return self.cache[doi]
        # Defense-in-depth: the DOI comes from repo files, so pin its shape
        # and only ever hit the two allow-listed hosts over HTTPS.
        if not _STRICT_DOI_RE.match(doi):
            result: tuple[str, dict | None] = ("error", {"detail": f"strict shape check failed: {doi!r}"})
            self.cache[doi] = result
            return result
        prefix = doi.split("/", 1)[0]
        template = DATACITE_API if prefix in DATACITE_PREFIXES else CROSSREF_API
        url = template.format(doi=urllib.request.quote(doi, safe=""))
        req = urllib.request.Request(url, headers={"User-Agent": f"EduEvidence-doi-audit/1.0 (mailto:{MAILTO})"})
        result = ("error", None)
        for attempt in range(2):
            try:
                with self.opener.open(req, timeout=20) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    message = payload.get("message", payload.get("data", {}))
                    if isinstance(message, dict) and "attributes" in message:
                        attrs = message["attributes"]  # DataCite JSON:API envelope
                        titles = [t.get("title") for t in attrs.get("titles", []) if t.get("title")]
                        message = {"title": titles}
                    result = ("ok", message)
                break
            except urllib.error.HTTPError as exc:
                result = ("not_found", {"status": exc.code}) if exc.code == 404 else ("error", {"status": exc.code})
                break
            except (urllib.error.URLError, http.client.RemoteDisconnected, ConnectionError,
                    TimeoutError, OSError, json.JSONDecodeError) as exc:
                result = ("error", {"detail": str(exc)})
                if attempt == 0:
                    time.sleep(1.5)
        time.sleep(self.sleep_s)
        self.cache[doi] = result
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples-dir", default="examples")
    parser.add_argument("--sleep", type=float, default=0.3, help="seconds between registry calls")
    parser.add_argument("--no-fail", action="store_true", help="always exit 0")
    args = parser.parse_args()

    records_dir = REPO_ROOT / args.examples_dir
    if not records_dir.is_dir():
        print(f"FAIL: {records_dir} not found")
        return 2

    paired, occurrences = collect(records_dir)
    print(f"collected {len(paired)} unique DOIs ({occurrences} occurrences) under {records_dir}")

    client = RegistryClient(args.sleep)
    rows = []
    counts: defaultdict[str, int] = defaultdict(int)
    items = sorted(paired.items())
    for i, (doi, info) in enumerate(items, 1):
        local_title = max(info["titles"], key=lambda t: info["titles"][t]) if info["titles"] else None
        status, msg = client.fetch(doi)
        cr_title = None
        if isinstance(msg, dict):
            titles = msg.get("title") or []
            cr_title = titles[0] if titles else None
        similarity = _overlap(local_title, cr_title) if status == "ok" else None
        if status == "ok" and similarity is not None and similarity < OVERLAP_THRESHOLD:
            status = "mismatch"
        counts[status] += 1
        rows.append({
            "doi": doi,
            "status": status,
            "local_titles": sorted(info["titles"]),
            "files": info["files"],
            "crossref_title": cr_title,
            "title_overlap": round(similarity, 3) if similarity is not None else None,
        })
        print(f"[{i}/{len(items)}] {status:9s} {doi}")

    out_dir = REPO_ROOT / "benchmarks" / "doi-audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "unique_dois": len(paired),
                    "counts": dict(counts),
                    "results": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    lines = ["# DOI Audit Report", "",
             f"生成时间：{time.strftime('%Y-%m-%d %H:%M %Z')}；数据源：api.crossref.org / api.datacite.org",
             f"唯一 DOI：{len(paired)}；分类：{dict(counts)}",
             "判定说明：not_found=注册表无此 DOI；mismatch=解析成功但标题指向其他论文（阈值 "
             f"{OVERLAP_THRESHOLD}，需人工复核边界案例）。", ""]
    bad = [r for r in rows if r["status"] != "ok"]
    if bad:
        lines += ["## 需处理（mismatch / not_found / error）", ""]
        for r in bad:
            lt = "; ".join(r["local_titles"])[:90].replace("|", "\\|") or "（无配对标题）"
            ct = (r["crossref_title"] or "")[:70].replace("|", "\\|")
            lines.append(f"- **{r['status']}** `{r['doi']}`")
            lines.append(f"  - 本地标题：{lt}")
            if ct:
                lines.append(f"  - 注册表标题：{ct}")
            lines.append(f"  - 出现文件：{', '.join(r['files'])}")
    good = [r for r in rows if r["status"] == "ok"]
    if good:
        lines += ["", f"## 通过（{len(good)} 条）", "", "| DOI | 标题重合度 | 出现文件 |", "|---|---|---|"]
        for r in good:
            sim = "—" if r["title_overlap"] is None else r["title_overlap"]
            files = ", ".join(r["files"])
            lines.append(f"| `{r['doi']}` | {sim} | {files} |")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nsummary: {dict(counts)} -> {out_dir}/report.(json|md)")
    fatal = sum(counts[s] for s in ("not_found", "mismatch", "error"))
    if fatal and not args.no_fail:
        print(f"FAIL: {fatal} DOI(s) need attention")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
