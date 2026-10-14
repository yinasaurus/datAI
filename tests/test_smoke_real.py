"""Smoke-script helpers. These tests do not call the model."""

from pathlib import Path

import pytest

from scripts.smoke_real import (
    BudgetClient,
    CallBudget,
    CallBudgetExceeded,
    cache_label,
    dev_scenario_paths,
    parse_args,
)

ROOT = Path(__file__).resolve().parents[1]


def test_override_flag_is_repeatable() -> None:
    args = parse_args(
        ["--n", "2", "--max-calls", "10", "--override", "max_revisions=0", "--override", "setup=A"]
    )

    assert args.n == 2
    assert args.max_calls == 10
    assert args.override == ["max_revisions=0", "setup=A"]


def test_dev_scenarios_are_taken_in_filename_order() -> None:
    paths = dev_scenario_paths(ROOT, 3)

    assert [path.name for path in paths] == ["s_001.json", "s_002.json", "s_003.json"]


def test_budget_refuses_the_call_that_would_pass_the_cap() -> None:
    class Inner:
        def __init__(self) -> None:
            self.calls = 0
            self.models = self

        def generate_content(self, *, model: str, contents: str, config: object) -> str:
            self.calls += 1
            return "sent"

    inner = Inner()
    client = BudgetClient(inner, CallBudget(1))

    assert client.generate_content(model="m", contents="c", config=None) == "sent"
    with pytest.raises(CallBudgetExceeded):
        client.generate_content(model="m", contents="c", config=None)

    assert inner.calls == 1


def test_cache_label() -> None:
    assert cache_label([{"cached": False}]) == "no"
    assert cache_label([{"cached": True}]) == "yes"
    assert cache_label([{"cached": True}, {"cached": False}]) == "partial"
