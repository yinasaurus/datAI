"""Run setup A on one scenario and print the plan plus the checker report."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from tripbot.checker.check_plan import check_plan
from tripbot.config import load_config
from tripbot.planning.registry import make_plan
from tripbot.schemas import load_places, load_scenario, load_travel_times


def main(argv: list[str] | None = None) -> int:
    """Load one scenario, call setup A, and print the plan and the report."""
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Run setup A on one scenario")
    parser.add_argument(
        "--scenario",
        type=Path,
        default=ROOT / "data" / "scenarios" / "dev" / "s_001.json",
    )
    args = parser.parse_args(argv)
    config = load_config(ROOT / "config.yaml", [])
    if not os.environ.get("GEMINI_API_KEY"):
        print("Put GEMINI_API_KEY in .env (copy .env.example).")
        return 1
    if config["model"] == "REPLACE_WITH_EXACT_MODEL_NAME":
        print("Set config.yaml model to the exact Gemini model id.")
        return 1

    scenario = load_scenario(args.scenario)
    places = load_places(ROOT / config["paths"]["places"])
    travel_times = load_travel_times(ROOT / config["paths"]["travel_times"])
    config["days"] = scenario.days
    result = make_plan("A", scenario.friends, places, travel_times, config)
    print(f"scenario {scenario.id} setup A")
    print(
        f"calls {result.llm_calls} tokens_in {result.tokens_in} "
        f"tokens_out {result.tokens_out} seconds {result.seconds:.2f}"
    )
    if result.plan is None:
        print("plan failed")
        for step in result.trace:
            print(step)
        return 1

    print(result.plan.model_dump_json(indent=2))
    report = check_plan(result.plan, scenario.friends, places, travel_times, config)
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
