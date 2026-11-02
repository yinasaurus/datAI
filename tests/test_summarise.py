"""Offline analysis checks with deliberately unbalanced and incomplete results."""
import json
from pathlib import Path

import pytest

from tripbot.eval.summarise import condition_summary, failure_rows, load_experiment, main, paired_summary


def row(scenario, condition="A", repetition=1, status="success", score=0.5):
    success = status == "success"
    return {"job_id": f"{scenario}__{condition}__r{repetition}", "scenario_id": scenario,
            "condition": condition, "repetition": repetition, "status": status,
            "dataset": "test-dev", "prompt_version": "3", "task_success": success,
            "delivered_minimum": score if success else 0,
            "delivered_mean": score if success else 0, "elapsed_seconds": 2.0,
            "usage": {"physical_requests": 2, "logical_calls": 1, "tokens_in": 10, "tokens_out": 5},
            "report": {"violations": [], "hard_limit_satisfaction": 1.0} if success else None}


def test_scenarios_receive_equal_weight_despite_unequal_repetition_counts():
    rows = [row("one", repetition=i, score=1) for i in (1, 2, 3)] + [row("two", score=0)]
    summary = condition_summary("A", 6, rows)
    assert summary["delivered_minimum"] == 0.5  # Not the pooled-job mean 0.75.
    assert summary["delivered_minimum_jobs"] == 4
    assert summary["delivered_minimum_scenarios"] == 2


def test_api_failures_and_unknown_usage_have_explicit_denominators():
    rows = [row("one"), row("one", repetition=2, status="api_failure")]
    rows[1]["usage"]["tokens_in"] = None
    summary = condition_summary("A", 3, rows)
    assert summary["task_success_completed"] == 1
    assert summary["task_success_completed_jobs"] == 1
    assert summary["task_delivery"] == 0.5
    assert summary["completion_rate"] == 0.5
    assert summary["delivered_minimum"] == 0.25
    assert summary["tokens_in"] == 10
    assert summary["tokens_in_jobs"] == 1
    missing = condition_summary("B", 3, rows)
    assert missing["task_delivery"] is None
    assert missing["recorded"] == 0


def test_pairs_match_scenarios_and_keep_incomplete_pairs_visible():
    rows = [row("one", "B", score=0), row("one", "C2", score=0.5), row("two", "C2", score=1)]
    jobs = [{**r, "job_id": r["job_id"] + str(i)} for r in rows for i in (1, 2, 3)]
    paired = next(p for p in paired_summary(rows, jobs)
                  if p["comparison"] == "C2-B" and p["metric"] == "delivered_minimum")
    assert paired["matched_scenarios"] == 1
    assert paired["complete_matched_scenarios"] == 0
    assert paired["difference"] == 0.5
    assert paired["wins"] == 1


def test_failure_counts_distinguish_occurrences_from_jobs_and_hard_limits():
    bad = row("one", status="constraint_failure")
    bad["report"] = {"violations": [{"type": "over_budget", "detail": "Amy"},
                                    {"type": "over_budget", "detail": "Ben"}],
                     "hard_limit_satisfaction": 0.5}
    counts, details = failure_rows([bad])
    budget = next(c for c in counts if c["type"] == "over_budget")
    assert budget["affected_jobs"] == 1 and budget["occurrences"] == 2
    assert any(c["type"] == "hard_limit_failure" for c in counts)
    assert len(details) == 3


def fixture(tmp_path, results):
    jobs = [{key: r[key] for key in ("job_id", "scenario_id", "condition", "repetition")} for r in results]
    jobs.append({"job_id": "pending", "scenario_id": "two", "condition": "A", "repetition": 1})
    (tmp_path / "manifest.json").write_text(json.dumps({"dataset": "test-dev", "prompt_version": "3",
                                                       "conditions": ["A", "B"]}))
    (tmp_path / "schedule.json").write_text(json.dumps(jobs))
    (tmp_path / "state.json").write_text(json.dumps({**{r["job_id"]: r["status"] for r in results},
                                                     "pending": "pending"}))
    (tmp_path / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results))


def test_summary_writes_readable_report_without_hiding_missing_jobs(tmp_path):
    fixture(tmp_path, [row("one")])
    assert main([str(tmp_path)]) == 0
    report = (tmp_path / "analysis" / "summary.md").read_text()
    assert "1/2" in report
    assert "Incomplete pilot" in report
    assert "| B | 0/0 | 0 | —" in report
    with pytest.raises(SystemExit):
        main([str(tmp_path)])


def test_duplicate_results_are_rejected(tmp_path):
    entry = row("one")
    fixture(tmp_path, [entry])
    with (tmp_path / "runs.jsonl").open("a") as handle:
        handle.write(json.dumps(entry) + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_experiment(tmp_path)


def test_dry_run_has_no_invented_zero_scores(tmp_path):
    fixture(tmp_path, [])
    assert main([str(tmp_path)]) == 0
    data = json.loads((tmp_path / "analysis" / "summary.json").read_text())
    assert data["recorded"] == 0
    assert all(r["task_delivery"] is None for r in data["conditions"])
