"""Independent expected bounds for the fictional budget-choice benchmark."""
import json
from pathlib import Path

import pytest

from scripts.generate_synthetic_dev import build_scenarios, build_world, audit_scenario
from scripts.validate_scenarios import validate_scenarios
from tripbot.config import load_config
from tripbot.schemas import Plan, load_scenario
from tripbot.checker.check_plan import check_plan

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("n", [2, 3, 5])
def test_synthetic_world_is_fictional_and_validates(n):
    folder = ROOT / "data" / "synthetic_v1" / f"n{n}"
    places, catalog, travel = build_world(n)
    assert all(not p.verified and p.name.startswith("FICTIONAL") for p in places)
    assert all(p.source.startswith("synthetic:") for p in places)
    assert validate_scenarios(folder / "dev", config_path=folder / "config.yaml") == []
    config = load_config(folder / "config.yaml", [])
    for scenario in build_scenarios(n):
        assert load_scenario(folder / "dev" / f"{scenario.id}.json") == scenario
        row = audit_scenario(scenario, places, config)
        cap = min(p.budget for p in scenario.friends.values())
        # Each unique b-tag requires its cost-six private place. The shared
        # cost-three place gives everyone a; upgrades buy b for six each.
        expected_min = 1.0 if cap >= 6 * n else 0.5
        expected_mean = 1.0 if cap >= 6 * n else 0.5 + min(n, (cap - 3) // 6) / (2 * n)
        assert row["optimal_minimum_satisfaction"] == expected_min
        assert row["optimal_mean_subject_to_maximum_minimum"] == pytest.approx(expected_mean)
        assert row["all_friends_full_satisfaction_feasible"] == (cap >= 6 * n)
        assert row["distinct_satisfaction_vectors"] >= 2
        for name, witness in row["individual_full_satisfaction_witnesses"].items():
            report = check_plan(Plan.model_validate(witness["plan"]), scenario.friends,
                                places, travel, config)
            assert report.task_success
            assert report.per_friend_satisfaction[name] == 1
        assert row["optimal_report"]["task_success"]
        if cap == 6 * (n - 1):
            alternative = row["zero_minimum_alternative"]
            assert alternative is not None
            assert alternative["report"]["fairness"]["min"] == 0
            scores = alternative["report"]["per_friend_satisfaction"].values()
            assert sum(scores) / n == pytest.approx(row["optimal_mean_subject_to_maximum_minimum"])


def test_saved_audit_is_reproducible_and_development_only():
    folder = ROOT / "data" / "synthetic_v1"
    saved = json.loads((folder / "development_audit.json").read_text())
    rebuilt = []
    for n in (2, 3, 5):
        config = load_config(folder / f"n{n}" / "config.yaml", [])
        places, _, _ = build_world(n)
        rebuilt.extend(audit_scenario(scenario, places, config) for scenario in build_scenarios(n))
    assert saved == rebuilt
    assert len(saved) == 8
    assert not list(folder.rglob("heldout"))
