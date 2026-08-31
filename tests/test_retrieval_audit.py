import json

from retrieval.audit import AuditedSearchExecutor, SearchPlan
from retrieval.search import SearchHit


class Provider:
    name = "fixture"

    def search(self, query, limit=10):
        return [SearchHit("Same paper", "https://doi.org/10.1/example", "metadata", self.name, doi="10.1/example")]


def test_audited_search_writes_plan_attempts_and_screening(tmp_path):
    plan = SearchPlan.from_question("Does intervention work?", concepts=("intervention",))
    results = AuditedSearchExecutor([Provider()]).execute(plan, tmp_path)
    assert len(results) == 1
    provenance = json.loads((tmp_path / "search-provenance.json").read_text())
    assert provenance["counter_evidence_queries_executed"] == 1
    assert (tmp_path / "search-attempts.jsonl").read_text().count("success") == 3
    assert (tmp_path / "source-screening.csv").is_file()
    assert (tmp_path / "exclusion-log.csv").is_file()
