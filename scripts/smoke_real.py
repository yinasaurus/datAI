"""Run setups A, B, and C on a few development scenarios with the configured model.

Each line reports whether the reply was a valid plan, the checker summary,
token counts, seconds, planning calls, and whether the cache served the call.
``--max-calls`` counts requests sent to the API. Cache hits are not counted.
The script refuses the request that would pass the cap.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from tripbot.checker.check_plan import check_plan
from tripbot.config import load_config
from tripbot.planning.registry import PlanResult, make_plan
from tripbot.schemas import Report, Scenario, load_places, load_scenario, load_travel_times


class CallBudgetExceeded(RuntimeError):
    """Raised before an API request that would pass ``--max-calls``."""

    def __init__(self, used: int, limit: int) -> None:
        self.used = used
        self.limit = limit
        super().__init__(f"{used} real calls used, limit {limit}")


class CallBudget:
    """How many API requests the smoke run may still send."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0

    def take(self) -> None:
        """Reserve one real call, or refuse before it is sent."""
        if self.used + 1 > self.limit:
            raise CallBudgetExceeded(self.used, self.limit)
        self.used += 1


class BudgetClient:
    """Gemini client wrapper that applies a :class:`CallBudget`."""

    def __init__(self, inner: Any, budget: CallBudget) -> None:
        self._inner = inner
        self._budget = budget
        self.models = self

    def generate_content(self, *, model: str, contents: str, config: object) -> Any:
        self._budget.take()
        return self._inner.models.generate_content(model=model, contents=contents, config=config)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Read ``--n``, ``--max-calls``, and repeatable ``--override key=value``."""
    parser = argparse.ArgumentParser(description="Smoke setups A, B, and C on dev scenarios")
    parser.add_argument("--n", type=int, default=3, help="how many dev scenarios to run")
    parser.add_argument(
        "--max-calls",
        type=int,
        default=60,
        help="stop before this many real API requests",
    )
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        metavar="key=value",
        help="repeatable config override passed to load_config",
    )
    return parser.parse_args(argv)


def dev_scenario_paths(root: Path, n: int) -> list[Path]:
    """First ``n`` development scenarios in filename order."""
    return sorted((root / "data" / "scenarios" / "dev").glob("*.json"))[:n]


def cache_label(trace: list[dict[str, Any]]) -> str:
    """``yes`` when every call was cached, ``partial`` when some were, else ``no``."""
    flags = [bool(step.get("cached")) for step in trace]
    if flags and all(flags):
        return "yes"
    if any(flags):
        return "partial"
    return "no"


def summarize(scenario_id: str, setup: str, result: PlanResult, report: Report | None) -> str:
    """One smoke line: plan validity, checker summary, cost, and cache."""
    if report is None:
        feasible = "no"
        violations = "invalid_plan"
        hard_limit = "-"
        fairness = "-"
    else:
        feasible = "yes" if report.feasible else "no"
        violations = ",".join(item.type for item in report.violations) or "none"
        hard_limit = f"{report.hard_limit_satisfaction:.2f}"
        fairness = (
            f"min={report.fairness.min:.2f} gap={report.fairness.gap:.2f} "
            f"jain={report.fairness.jain:.2f}"
        )
    valid = "yes" if result.plan is not None else "no"
    return (
        f"{scenario_id} setup={setup} valid_json={valid} feasible={feasible} "
        f"violations={violations} hard_limit_satisfaction={hard_limit} "
        f"fairness={fairness} tokens_in={result.tokens_in} tokens_out={result.tokens_out} "
        f"seconds={result.seconds:.2f} calls={result.llm_calls} cache_hit={cache_label(result.trace)}"
    )


def _gemini_client() -> Any:
    from google import genai
    from google.genai import types

    return genai.Client(
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=1),
        )
    )


def _run_one(
    setup: str,
    scenario: Scenario,
    places: list[Any],
    travel: Any,
    config: dict[str, Any],
    client: BudgetClient,
) -> str:
    config["days"] = scenario.days
    result = make_plan(setup, scenario.friends, places, travel, config, client=client)
    report = None
    if result.plan is not None:
        report = check_plan(result.plan, scenario.friends, places, travel, config)
    return summarize(scenario.id, setup, result, report)


def main(argv: list[str] | None = None) -> int:
    """Smoke A, B, and C. Returns 0 when the run finishes or the call cap stops it."""
    load_dotenv(ROOT / ".env")
    args = parse_args(argv)
    if args.n < 1:
        print("--n must be at least 1")
        return 2
    if args.max_calls < 0:
        print("--max-calls must be at least 0")
        return 2

    config = load_config(ROOT / "config.yaml", args.override)
    if not os.environ.get("GEMINI_API_KEY"):
        print("Put GEMINI_API_KEY in .env (copy .env.example).")
        return 1
    if config["model"] == "REPLACE_WITH_EXACT_MODEL_NAME":
        print("Set config.yaml model to the exact Gemini model id.")
        return 1

    scenarios = dev_scenario_paths(ROOT, args.n)
    if len(scenarios) < args.n:
        print(f"found {len(scenarios)} dev scenarios, --n asked for {args.n}")
        return 1

    places = load_places(ROOT / config["paths"]["places"])
    travel = load_travel_times(ROOT / config["paths"]["travel_times"])
    budget = CallBudget(args.max_calls)
    client = BudgetClient(_gemini_client(), budget)
    print(
        f"model={config['model']} max_revisions={config['max_revisions']} "
        f"negotiation_rounds={config['negotiation_rounds']} setup={config['setup']} "
        f"guardrails={config['guardrails']} max_calls={args.max_calls}"
    )

    for path in scenarios:
        scenario = load_scenario(path)
        for setup in ("A", "B", "C"):
            if budget.used >= budget.limit:
                print(
                    f"stopped before {scenario.id} setup {setup}: "
                    f"{budget.used} real calls used, limit {budget.limit}"
                )
                return 0
            try:
                print(_run_one(setup, scenario, places, travel, config, client))
            except CallBudgetExceeded as exc:
                print(f"stopped during {scenario.id} setup {setup}: {exc}")
                return 0
    print(f"real_calls {budget.used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
