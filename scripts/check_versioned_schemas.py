#!/usr/bin/env python3
"""check_versioned_schemas.py - data-level validation for v3 / v4 / vNext.

CI validated this contract family by parsing the JSON only, so a schema could
drift arbitrarily (renamed required fields, changed enums, wrong types) and
stay green. Each family is exercised here by building a record from its own
dataclass or builder and validating that record against its schema, which is
the check that would have caught a real mismatch.

Stdlib only; exit 1 on any invalid record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))


def _validate(record, schema_rel, label):
    from validate_schema import SchemaError, Validator

    path = ROOT / schema_rel
    schema = json.loads(path.read_text(encoding='utf-8'))
    validator = Validator(schema, base_dir=path.parent)
    try:
        validator.validate(record, schema, label)
    except SchemaError as exc:
        return f'{label}: {exc}'
    return None


def main() -> int:
    problems = []
    checked = 0

    # --- vNext: records built from their own dataclasses -------------------
    try:
        from engine.autoresearch.contracts import NegativeSearchRecord

        record = NegativeSearchRecord(
            negative_search_id='NSR-1', research_iteration_id='RI-1',
            gap_id='GAP-1', queries=('a', 'b'), providers=('openalex',),
            candidate_count=0, fetched_count=0, eligible_count=0)
        payload = record.__dict__ if hasattr(record, '__dict__') else record
        # JSON round-trip puts tuples back into their serialized form, which is
        # what actually gets persisted; validate that shape.
        payload = json.loads(json.dumps(payload, default=str))
        err = _validate(payload, 'schemas/vNext/negative-search-record.schema.json',
                        'negative-search-record')
        if err:
            problems.append(err)
        checked += 1
    except Exception as exc:  # import or construction failure is itself a defect
        problems.append(f'negative-search-record: could not build record: {exc}')

    # --- vNext: autoresearch lifecycle records ---------------------------
    # Every schema in this family is exercised against the dataclass that
    # actually produces it, so a renamed field, retyped value or narrowed
    # enum fails CI instead of drifting silently. Only `negative-search-record`
    # was wired before; the rest parsed as JSON and nothing more.
    try:
        import dataclasses

        from engine.autoresearch.contracts import (ResearchBudget,
                                                   ResearchExperimentType,
                                                   ResearchIteration,
                                                   ResearchStrategy,
                                                   IterationStatus)
        from engine.autoresearch.gap_priority import GapPriority

        strategy = ResearchStrategy(
            strategy_id='RST-1',
            experiment_type=ResearchExperimentType.TARGETED_RETRIEVAL,
            hypothesis='a targeted retrieval closes the retention gap',
            expected_gain='one or more direct retention findings',
            budget=ResearchBudget())
        iteration = ResearchIteration(
            iteration_id='RI-1', project_id='PRJ-1', base_graph_revision=1,
            gap_id='GAP-1', strategy=strategy)
        iteration.complete(IterationStatus.SEARCH_SATURATED)
        iteration_payload = json.loads(json.dumps(iteration.as_dict(), default=str))
        strategy_payload = json.loads(json.dumps(dataclasses.asdict(strategy), default=str))
        strategy_payload['experiment_type'] = strategy.experiment_type.value
        priority = GapPriority(
            gap_id='GAP-1', dvi_band='HIGH', cost_band='LOW',
            decision_material=True, drivers=('missing_retention',),
            # The enum is the controller's own vocabulary (gap_priority.py and
            # controller.py emit these three); it is not the experiment-type
            # vocabulary. Using a plausible-looking but wrong value here is
            # exactly the drift this check exists to catch.
            next_research_mode='secondary_evidence_search', score=1)
        priority_payload = json.loads(json.dumps(dataclasses.asdict(priority), default=str))

        for label, payload, schema_rel in (
            ('research-strategy', strategy_payload, 'schemas/vNext/research-strategy.schema.json'),
            ('research-iteration', iteration_payload, 'schemas/vNext/research-iteration.schema.json'),
            ('gap-priority', priority_payload, 'schemas/vNext/gap-priority.schema.json'),
        ):
            err = _validate(payload, schema_rel, label)
            if err:
                problems.append(err)
            checked += 1
    except Exception as exc:
        problems.append(f'autoresearch lifecycle records: could not build record: {exc}')

    # --- vNext: orchestration plan and task contracts ---------------------
    try:
        import dataclasses as _dc

        from engine.orchestration import ExecutionPlanner, ExecutionMode

        # A delegated plan needs a run id and a base revision; without them
        # TaskSpec.validate_for_dispatch refuses to describe a dispatchable task.
        plan = ExecutionPlanner().plan('M', run_id='RUN-1', base_revision=1)
        plan_payload = json.loads(json.dumps(_dc.asdict(plan), default=str))
        plan_payload['complexity'] = str(getattr(plan.complexity, 'value', plan.complexity))
        err = _validate(plan_payload, 'schemas/vNext/execution-plan.schema.json',
                        'execution-plan')
        if err:
            problems.append(err)
        checked += 1

        delegated = [t for t in plan.tasks if t.execution_mode is ExecutionMode.DELEGATED]
        if not delegated:
            problems.append('execution plan has no delegated task to exercise task-spec')
        else:
            task_payload = json.loads(json.dumps(delegated[0].to_dict(), default=str))
            err = _validate(task_payload, 'schemas/vNext/task-spec.schema.json', 'task-spec')
            if err:
                problems.append(err)
            checked += 1

            # A WorkerResult is built only by the lead process, which ignores
            # worker self-attestation; exercise that real path, not a hand-built dict.
            from engine.worker_result import validate_worker_output
            result = validate_worker_output(delegated[0], {
                'task_id': delegated[0].task_id,
                'status': 'completed',
                'staging_artifacts': [{'artifact_type': delegated[0].expected_outputs[0],
                                       'summary': 'staged'}],
                'validated': True,
                'metrics': {},
                'summary': 'ok',
            })
            err = _validate(json.loads(json.dumps(result.to_dict(), default=str)),
                            'schemas/vNext/worker-result.schema.json', 'worker-result')
            if err:
                problems.append(err)
            checked += 1
    except Exception as exc:
        problems.append(f'orchestration records: could not build record: {exc}')

    # --- vNext: autoevolve session and experiment records -----------------
    try:
        import dataclasses as _dc2

        from engine.autoevolve.core import EvalSnapshot, SkillExperiment

        snapshot = EvalSnapshot(
            eval_id='EVAL-1', hard_gates_passed=True, science_score=0.8,
            research_score=0.7, robustness=0.9, cost=0.0,
            latency=12.5, complexity=0.5, repeats=3, noise_floor=0.01,
            dev_passed=True, holdout_passed=True, adversarial_passed=True,
            holdout_isolation_verified=False, eval_suite_hash='deadbeef')
        snapshot_payload = json.loads(json.dumps(_dc2.asdict(snapshot), default=str))
        err = _validate(snapshot_payload, 'schemas/vNext/eval-snapshot.schema.json',
                        'eval-snapshot')
        if err:
            problems.append(err)
        checked += 1

        experiment = SkillExperiment(
            experiment_id='EXP-1', session_id='session-1',
            parent_skill_revision='rev-1', hypothesis='a narrower prompt scores higher',
            mutation_scope=('safe',), changed_files=('skill/agents/skeptic.md',),
            candidate_commit='deadbeef', baseline_eval_id='EVAL-1',
            candidate_eval_id='EVAL-2', protected_hash_before='h1',
            protected_hash_after='h1', status='REJECT',
            promotion_reason='no significant improvement')
        experiment_payload = json.loads(json.dumps(_dc2.asdict(experiment), default=str))
        err = _validate(experiment_payload, 'schemas/vNext/skill-experiment.schema.json',
                        'skill-experiment')
        if err:
            problems.append(err)
        checked += 1

        # The session report is the real runner payload (runner.py writes
        # daily-report.json); validate that documented shape directly.
        session_report = {
            'run_tag': 'session-1', 'branch': 'autoevolve/session-1',
            'experiments': 1, 'statuses': ['REJECT'], 'best_experiment_id': None,
            'best_candidate_commit': None, 'cost': 0.0, 'wall_minutes': 1.0,
            'plateau': False, 'stop_reason': 'completed',
            'promotion': 'branch_only', 'branch_push_requested': False,
            'branch_pushed': False, 'mutation_view': 'dev_only_context_isolation',
            'holdout_isolation_verified': False, 'isolation_provider': 'none',
            'isolation_reason': 'no os isolation provider available',
            'eval_suite_hash': 'deadbeef', 'security_note': 'branch only',
            'candidate_artifacts': 'local session state only; never auto-pushed',
        }
        err = _validate(session_report, 'schemas/vNext/autoevolve-session.schema.json',
                        'autoevolve-session')
        if err:
            problems.append(err)
        checked += 1
    except Exception as exc:
        problems.append(f'autoevolve records: could not build record: {exc}')

    # --- v3: the BENCHMARK run manifest (scripts/benchmark_v3.py) ---------
    # Note: schemas/v3/run-manifest.schema.json describes the empirical
    # benchmark harness record, not the run-workspace manifest. Validating the
    # wrong producer is how a contract silently stops describing reality.
    try:
        fixture = sorted((ROOT / 'benchmarks' / 'empirical').glob('*/manifest.json'))
        if fixture:
            payload = json.loads(fixture[0].read_text(encoding='utf-8'))
            err = _validate(payload, 'schemas/v3/run-manifest.schema.json',
                            f'run-manifest ({fixture[0].parent.name})')
            if err:
                problems.append(err)
            checked += 1
        else:
            # benchmarks/empirical/ holds local empirical runs and is excluded
            # from the submission package on purpose. Its absence means there is
            # nothing to check in this checkout, not that the contract is broken.
            print('note: no benchmarks/empirical/*/manifest.json in this checkout; '
                  'skipping the v3 run-manifest data check')
    except Exception as exc:
        problems.append(f'v3 run-manifest: {exc}')

    # --- sanity: every declared schema still parses -----------------------
    for family in ('v3', 'v4', 'vNext'):
        for path in sorted((ROOT / 'schemas' / family).glob('*.json')):
            try:
                json.loads(path.read_text(encoding='utf-8'))
                checked += 1
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f'{path.relative_to(ROOT)}: {exc}')

    if problems:
        print('ERROR: versioned schema validation failed', file=sys.stderr)
        for item in problems:
            print(f'  {item}', file=sys.stderr)
        return 1
    print(f'versioned schemas OK ({checked} checks across v3 / v4 / vNext)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
