"""Run a reproducible, sequential A/B/C planning experiment (no calls on --dry-run)."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import importlib.metadata
import platform
import random
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from google.genai.errors import APIError

from tripbot.checker.check_plan import check_plan
from tripbot.config import load_config
from tripbot.eval.capture import CaptureClient, error_info, redact, utc_now, write_json
from tripbot.llm import BACKOFF_SECONDS, CALL_OBSERVER, MAX_ATTEMPTS, _build_client
from tripbot.planning.prompts import PROMPT_VERSION
from tripbot.planning.registry import make_plan
from tripbot.schemas import load_places, load_scenario, load_tag_catalog, load_travel_times

ROOT = Path(__file__).resolve().parents[2]
CONDITIONS = {"A": ("A", 0), "B": ("B", 0), "C2": ("C", 2), "C0": ("C", 0)}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schedule(scenarios: list[Any], conditions: list[str], runs: int, seed: int) -> list[dict]:
    """Shuffle all conditions together while retaining stable job identities."""
    jobs = [{"job_id": f"{s.id}__{condition}__r{run}", "scenario_id": s.id,
             "condition": condition, "repetition": run}
            for s in scenarios for run in range(1, runs + 1) for condition in conditions]
    random.Random(seed).shuffle(jobs)
    return jobs


def source_snapshot(output: Path) -> dict:
    """Capture relevant source, including untracked code, without copying env files."""
    files = []
    for folder in ("tripbot", "scripts", "tests"):
        files.extend(sorted((ROOT / folder).rglob("*.py")))
    files += [ROOT / name for name in ("config.yaml", "requirements.txt", "PROJECT_SPEC.md",
                                      "docs/archive/EVALUATION_PROTOCOL.md", "FINAL_EVALUATION_PROTOCOL.md", "pytest.ini")]
    hashes = {}
    for source in files:
        relative = source.relative_to(ROOT)
        target = output / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Source files have no secrets by contract; redact known credentials regardless.
        target.write_text(redact(source.read_text()), encoding="utf-8")
        hashes[str(relative)] = digest(source)
    def git(*args):
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else None
    return {"git_revision": (git("rev-parse", "HEAD") or "").strip() or None,
            "git_status": git("status", "--porcelain"), "source_hashes": hashes,
            "snapshot": "source/", "note": "snapshot includes uncommitted and untracked relevant source"}


def execute_job(job, scenario, places, travel, config, folder: Path, client) -> dict:
    folder.mkdir()
    capture = CaptureClient(client, folder / "calls.jsonl")
    run_config = copy.deepcopy(config)
    setup, rounds = CONDITIONS[job["condition"]]
    run_config.update(setup=setup, days=scenario.days, cache=False, negotiation_rounds=rounds)
    run_config["paths"]["llm_log"] = str(folder / "llm_log.jsonl")
    row = {**job, "started_utc": utc_now(), "setup": setup, "config": run_config,
           "prompt_version": PROMPT_VERSION, "scenario_factors": {
               "n_friends": scenario.n_friends, "conflict": scenario.conflict,
               "budget": scenario.budget, "split": scenario.split},
           "plan": None, "report": None, "trace": [], "task_success": None,
           "delivered_minimum": 0.0, "delivered_mean": 0.0,
           "delivered_per_friend": {name: 0.0 for name in scenario.friends},
           "calls_artifact": f"jobs/{job['job_id']}/calls.jsonl"}
    started = time.perf_counter()
    token = CALL_OBSERVER.set(capture)
    try:
        result = make_plan(setup, scenario.friends, places, travel, run_config, client=capture)
        row["verification_revisions"] = sum(t.get("step") == "revision" for t in result.trace)
        row["trace"] = result.trace
        row["model_call_seconds"] = result.seconds
        row["planner_logical_calls"] = result.llm_calls
        if result.plan is None:
            row.update(status="invalid_output", task_success=False)
        else:
            report = check_plan(result.plan, scenario.friends, places, travel, run_config)
            row.update(status="success" if report.task_success else "constraint_failure",
                       plan=result.plan.model_dump(), report=report.model_dump(),
                       task_success=report.task_success)
            if report.task_success:
                scores = list(report.per_friend_satisfaction.values())
                row.update(delivered_per_friend=report.per_friend_satisfaction,
                           delivered_minimum=report.fairness.min,
                           delivered_mean=sum(scores) / len(scores))
    except (APIError, httpx.TransportError, TimeoutError, ConnectionError) as exc:
        row.update(status="api_failure", error=error_info(exc))
    except KeyboardInterrupt:
        row.update(status="interrupted", delivered_minimum=None, delivered_mean=None, delivered_per_friend=None)
    except Exception as exc:
        row.update(status="experiment_error", error=error_info(exc),
                   delivered_minimum=None, delivered_mean=None, delivered_per_friend=None)
    finally:
        CALL_OBSERVER.reset(token)
    row.update(usage=capture.usage(), elapsed_seconds=time.perf_counter() - started,
               ended_utc=utc_now())
    write_json(folder / "result.json", row)
    return row


def main(argv: list[str] | None = None, *, client: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--scenarios", type=Path, required=True)
    parser.add_argument("--dataset", required=True, help="explicit dataset/world/version label")
    parser.add_argument("--split", choices=["dev", "heldout"], default="dev")
    parser.add_argument("--conditions", nargs="+", choices=list(CONDITIONS), default=list(CONDITIONS))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--schedule-seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True, help="fresh experiment directory")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dataset-manifest", type=Path)
    parser.add_argument("--require-clean", action="store_true", help="refuse an uncommitted code freeze")
    parser.add_argument("--max-jobs", type=int, help="execute a prefix; other jobs remain pending")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    if args.require_clean:
        status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
        if status.returncode or status.stdout.strip():
            parser.error("commit the evaluation freeze before --require-clean")
    if args.runs < 1 or (args.max_jobs is not None and args.max_jobs < 1):
        parser.error("runs and max-jobs must be positive")
    if len(args.conditions) != len(set(args.conditions)):
        parser.error("duplicate conditions would duplicate job IDs")
    output = args.output.resolve()
    if output.exists():
        parser.error("output exists; use a fresh directory (no overwrite or silent reruns)")
    config = load_config(args.config, [])
    config.update(cache=False)
    if config.get("temperature") != 0 or config.get("seed") != 42 or config.get("max_revisions") != 3:
        parser.error("protocol requires temperature=0, seed=42, max_revisions=3")
    if int(config.get("min_activities_per_day", 2)) != 2:
        parser.error("protocol requires two activities per day")
    if not config.get("model") or config["model"] == "REPLACE_WITH_EXACT_MODEL_NAME":
        parser.error("configure an accessible model ID first")
    # Resolve paths consistently from the repository, independent of shell cwd.
    for key in ("places", "tags", "travel_times"):
        config["paths"][key] = str((ROOT / config["paths"][key]).resolve())
    places = load_places(config["paths"]["places"])
    travel = load_travel_times(config["paths"]["travel_times"])
    catalog = load_tag_catalog(config["paths"]["tags"])
    if any(p.area not in travel.areas or not set(p.tags) <= set(catalog.tags) for p in places):
        parser.error("places must use the matching world vocabulary and travel areas")
    paths = sorted(args.scenarios.glob("*.json")) if args.scenarios.is_dir() else [args.scenarios]
    scenarios = [load_scenario(p) for p in paths]
    if not scenarios or any(s.split != args.split for s in scenarios):
        parser.error("scenario selection must be nonempty and match --split")
    if len({s.id for s in scenarios}) != len(scenarios):
        parser.error("scenario IDs must be unique")
    for scenario in scenarios:
        # IDs become filenames; reject traversal rather than sanitising identity.
        if not all(c.isalnum() or c in "_-" for c in scenario.id):
            parser.error("scenario IDs must contain only letters, numbers, underscores, or hyphens")
        for profile in scenario.friends.values():
            if not set(profile.likes) <= set(catalog.tags) or not set(profile.hard_limits) <= set(catalog.hard_limits):
                parser.error("scenario vocabulary does not match world config")
    dataset_metadata = None
    if args.dataset_manifest:
        dataset_metadata = json.loads(args.dataset_manifest.read_text())
        entries = dataset_metadata["scenarios"]
        if dataset_metadata["dataset"] != args.dataset or set(entries) != {s.id for s in scenarios}:
            parser.error("dataset manifest identity/selection mismatch")
        for scenario, path in zip(scenarios, paths):
            entry = entries[scenario.id]
            if entry["sha256"] != digest(path) or not entry.get("family_id") or entry.get("expected_feasible") is not True:
                parser.error("scenario hash/family/feasibility differs from final manifest")
        for key in ("places", "tags", "travel_times"):
            if dataset_metadata["world_hashes"][key] != digest(Path(config["paths"][key])):
                parser.error("world differs from validated dataset")
        for key, value in dataset_metadata["checker_config"].items():
            if config.get(key) != value:
                parser.error("checker configuration differs from validated dataset: " + key)
    jobs = schedule(scenarios, args.conditions, args.runs, args.schedule_seed)
    if dataset_metadata:
        for job in jobs:
            job.update(family_id=dataset_metadata["scenarios"][job["scenario_id"]]["family_id"], expected_feasible=True)
    output.mkdir(parents=True)
    (output / "jobs").mkdir()
    (output / "inputs").mkdir()
    hashes = {}
    for name, path in {"config.yaml": args.config, "places.json": Path(config["paths"]["places"]),
                       "tags.json": Path(config["paths"]["tags"]),
                       "travel_times.json": Path(config["paths"]["travel_times"]),
                       **{f"scenarios/{s.id}.json": p for s, p in zip(scenarios, paths)}}.items():
        target = output / "inputs" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(redact(path.read_text()), encoding="utf-8")
        hashes[name] = digest(path)
    if args.dataset_manifest:
        write_json(output / "inputs" / "dataset_manifest.json", dataset_metadata)
        hashes["dataset_manifest.json"] = digest(args.dataset_manifest)
    manifest = {"dataset_metadata": dataset_metadata, "method_version": "7", "dataset": args.dataset, "split": args.split, "created_utc": utc_now(),
                "dry_run": args.dry_run, "config": config, "runs": args.runs,
                "conditions": args.conditions, "schedule_seed": args.schedule_seed,
                "input_hashes": hashes, "prompt_version": PROMPT_VERSION,
                "retry_policy": {"max_requests_per_logical_call": MAX_ATTEMPTS,
                                 "backoff_seconds": BACKOFF_SECONDS},
                "source": source_snapshot(output),
                "environment": {"python": platform.python_version(), "platform": platform.platform(),
                    "packages": {name: importlib.metadata.version(name) for name in
                                 ("google-genai", "pydantic", "pyyaml", "python-dotenv", "httpx")}}}
    write_json(output / "manifest.json", manifest)
    write_json(output / "schedule.json", jobs)
    states = {job["job_id"]: "pending" for job in jobs}
    write_json(output / "state.json", states)
    print(f"Scheduled {len(jobs)} jobs; dataset={args.dataset}; cache=False; artifacts={output}")
    if args.dry_run:
        print("Dry run: no API calls; all jobs remain pending.")
        return 0
    load_dotenv(ROOT / ".env")
    if client is None:
        try:
            client = _build_client()
        except Exception as exc:
            write_json(output / "startup_error.json", error_info(exc))
            print("Client startup failed; jobs remain pending. See startup_error.json.")
            return 1
    by_id = {s.id: s for s in scenarios}
    for job in jobs[:args.max_jobs]:
        states[job["job_id"]] = "running"
        write_json(output / "state.json", states)
        row = execute_job(job, by_id[job["scenario_id"]], places, travel, config,
                          output / "jobs" / job["job_id"], client)
        states[job["job_id"]] = row["status"]
        write_json(output / "state.json", states)
        with (output / "runs.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(redact({"dataset": args.dataset, **row})) + "\n")
        print(f"{job['job_id']}: {row['status']} ({row['usage']['physical_requests']} requests)")
        if row["status"] in {"experiment_error", "interrupted"}:
            return 1
    print(f"Finished {sum(state != 'pending' for state in states.values())}/{len(states)} scheduled jobs; "
          f"pending={sum(state == 'pending' for state in states.values())}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
