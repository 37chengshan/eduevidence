from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "visualization" / "eduevidence-report" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import lieflat_engine as LE  # noqa: E402


def test_chart_selection_catalog_covers_registry_and_table_boundary():
    catalog_path = (
        ROOT
        / "visualization"
        / "eduevidence-report"
        / "references"
        / "chart-selection-catalog.md"
    )
    catalog = catalog_path.read_text(encoding="utf-8")
    assert "EvidenceMatrix" in catalog and "SourceList" in catalog
    assert "图负责模式识别，表负责精确核验" in catalog
    assert len(LE.REGISTRY) == 17
    for chart_type, reg in LE.REGISTRY.items():
        assert f"`{chart_type}`" in catalog, chart_type
        assert reg["catalog_ref"] in catalog, chart_type
        assert reg["extractor"] and reg["renderer"]

    skill = (
        ROOT / "skill" / "sub-skills" / "report-generation" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "chart-selection-catalog.md" in skill
    assert "visualization/lieflat-charts/catalog.md" not in skill
    assert "Tables are audit surfaces" in skill
