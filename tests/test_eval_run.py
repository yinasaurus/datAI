"""Runner integration checks: no Gemini or Telegram requests."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai.errors import ClientError

from tripbot.eval.run import main, schedule
from tripbot.schemas import load_scenario

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "data" / "synthetic_v1" / "n2"
GOOD = json.dumps({"days": [
    {"day": 1, "items": [{"place_id": "shared", "start": "10:00", "end": "11:00"},
                          {"place_id": "neutral_0", "start": "11:05", "end": "12:05"}]},
    {"day": 2, "items": [{"place_id": "neutral_1", "start": "10:00", "end": "11:00"},
                          {"place_id": "neutral_2", "start": "11:05", "end": "12:05"}]},
]})


class FakeClient:
    def __init__(self, items):
        self.items = list(items)
        self.models = self
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return SimpleNamespace(text=item, usage_metadata=SimpleNamespace(
            prompt_token_count=10, candidates_token_count=20, thoughts_token_count=2))


def args(tmp_path, *extra):
    return ["--config", str(WORLD / "config.yaml"), "--scenarios",
            str(WORLD / "dev" / "syn_n2_budget06.json"), "--dataset", "synthetic-v1-n2-dev",
            "--output", str(tmp_path / "experiment"), *extra]


def rows(tmp_path):
    return [json.loads(line) for line in (tmp_path / "experiment" / "runs.jsonl").read_text().splitlines()]


def test_dry_run_records_schedule_and_inputs_without_calls(tmp_path):
    client = FakeClient([])
    assert main(args(tmp_path, "--dry-run"), client=client) == 0
    folder = tmp_path / "experiment"
    jobs = json.loads((folder / "schedule.json").read_text())
    assert len(jobs) == 12
    assert len({j["job_id"] for j in jobs}) == 12
    assert {j["condition"] for j in jobs} == {"A", "B", "C0", "C2"}
    assert set(json.loads((folder / "state.json").read_text()).values()) == {"pending"}
    assert json.loads((folder / "manifest.json").read_text())["config"]["cache"] is False
    assert (folder / "inputs" / "places.json").exists()
    assert (folder / "source" / "tripbot" / "llm.py").exists()
    assert client.calls == 0
    with pytest.raises(SystemExit):
        main(args(tmp_path, "--dry-run"), client=client)


def test_schedule_reproducible_and_not_condition_blocked():
    scenario = load_scenario(WORLD / "dev" / "syn_n2_budget06.json")
    first = schedule([scenario], ["A", "B", "C0", "C2"], 3, 42)
    assert first == schedule([scenario], ["A", "B", "C0", "C2"], 3, 42)
    assert first != schedule([scenario], ["A", "B", "C0", "C2"], 3, 43)


def test_three_fresh_requests_capture_outputs_and_score(tmp_path):
    client = FakeClient([GOOD] * 3)
    assert main(args(tmp_path, "--conditions", "A"), client=client) == 0
    assert client.calls == 3
    for row in rows(tmp_path):
        assert row["status"] == "success"
        assert row["delivered_minimum"] == 0.5
        assert row["delivered_mean"] == 0.5
        assert row["usage"]["physical_requests"] == 1
        assert row["usage"]["logical_calls"] == 1
        assert row["usage"]["tokens_out"] == 22
        calls = (tmp_path / "experiment" / row["calls_artifact"]).read_text()
        assert GOOD in [e.get("text") for e in map(json.loads, calls.splitlines())]
        assert row["config"]["cache"] is False


@pytest.mark.parametrize("condition, calls", [("C0", 3), ("C2", 7)])
def test_c_ablation_uses_same_architecture_with_expected_calls(tmp_path, condition, calls):
    client = FakeClient([GOOD] * calls)
    assert main(args(tmp_path, "--conditions", condition, "--runs", "1"), client=client) == 0
    row = rows(tmp_path)[0]
    assert row["setup"] == "C"
    assert row["status"] == "success"
    assert row["usage"]["logical_calls"] == calls
    assert client.calls == calls


def test_retries_and_partial_usage_survive_terminal_failure(tmp_path, monkeypatch):
    # Avoid real sleeps, retaining the production retry policy and request count.
    import tripbot.llm as llm
    real_call = llm._call_llm
    delays = []
    def no_wait(*a, **kw):
        kw["sleeper"] = delays.append
        return real_call(*a, **kw)
    monkeypatch.setattr(llm, "_call_llm", no_wait)
    failure = ClientError(429, {"error": {"code": 429, "message": "quota"}})
    # B parses the first invalid response, then its correction exhausts retries.
    client = FakeClient(["bad-json"] + [failure] * 4)
    assert main(args(tmp_path, "--conditions", "B", "--runs", "1"), client=client) == 0
    row = rows(tmp_path)[0]
    assert row["status"] == "api_failure"
    assert row["task_success"] is None
    assert row["report"] is None
    assert row["delivered_minimum"] == 0
    assert row["usage"]["logical_calls"] == 2
    assert row["usage"]["physical_requests"] == 5
    assert row["usage"]["known_tokens_in"] == 10
    assert row["usage"]["tokens_in"] is None
    assert row["usage"]["unknown_usage_requests"] == 4
    assert delays == [1, 2, 4]


@pytest.mark.parametrize("response, status", [("bad-json", "invalid_output"), ('{"days": []}', "constraint_failure")])
def test_failed_plans_are_kept_with_zero_delivered_quality(tmp_path, response, status):
    assert main(args(tmp_path, "--conditions", "A", "--runs", "1"),
                client=FakeClient([response])) == 0
    row = rows(tmp_path)[0]
    assert row["status"] == status
    assert row["task_success"] is False
    assert row["delivered_minimum"] == 0


def test_programming_defect_stops_run_and_preserves_pending_jobs(tmp_path):
    assert main(args(tmp_path, "--conditions", "A"),
                client=FakeClient([RuntimeError("bug")])) == 1
    row = rows(tmp_path)[0]
    assert row["status"] == "experiment_error"
    assert row["delivered_minimum"] is None
    states = json.loads((tmp_path / "experiment" / "state.json").read_text())
    assert list(states.values()).count("pending") == 2


def test_missing_usage_is_unknown_and_limit_leaves_jobs_pending(tmp_path):
    client = FakeClient([])
    client.generate_content = lambda **kw: SimpleNamespace(text=GOOD, usage_metadata=None)
    assert main(args(tmp_path, "--conditions", "A", "--max-jobs", "1"), client=client) == 0
    row = rows(tmp_path)[0]
    assert row["usage"]["tokens_in"] is None
    assert row["usage"]["known_tokens_in"] == 0
    states = json.loads((tmp_path / "experiment" / "state.json").read_text())
    assert list(states.values()).count("pending") == 2


def test_known_secrets_are_redacted_from_saved_responses(tmp_path, monkeypatch):
    monkeypatch.setenv("CANARY_TOKEN", "SECRET-TEST-MARKER")
    assert main(args(tmp_path, "--conditions", "A", "--runs", "1"),
                client=FakeClient(["SECRET-TEST-MARKER"])) == 0
    calls = next((tmp_path / "experiment" / "jobs").glob("*/calls.jsonl")).read_text()
    assert "SECRET-TEST-MARKER" not in calls
    assert "[REDACTED]" in calls


def test_retry_success_keeps_request_count_and_unknown_usage(tmp_path, monkeypatch):
    import tripbot.llm as llm
    real_call = llm._call_llm
    def no_wait(*a, **kw):
        kw["sleeper"] = lambda delay: None
        return real_call(*a, **kw)
    monkeypatch.setattr(llm, "_call_llm", no_wait)
    client = FakeClient([TimeoutError("temporary"), GOOD])
    assert main(args(tmp_path, "--conditions", "A", "--runs", "1"), client=client) == 0
    row = rows(tmp_path)[0]
    assert row["status"] == "success"
    assert row["usage"]["logical_calls"] == 1
    assert row["usage"]["physical_requests"] == 2
    assert row["usage"]["tokens_in"] is None
    assert row["usage"]["known_tokens_in"] == 10


def test_interruption_is_not_a_fabricated_model_failure(tmp_path):
    assert main(args(tmp_path, "--conditions", "A"), client=FakeClient([KeyboardInterrupt()])) == 1
    row = rows(tmp_path)[0]
    assert row["status"] == "interrupted"
    assert row["task_success"] is None
    assert row["delivered_minimum"] is None
    assert list(json.loads((tmp_path / "experiment" / "state.json").read_text()).values()).count("pending") == 2
