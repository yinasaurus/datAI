"""Summarise one saved planning experiment offline, keeping missing jobs visible."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

TERMINAL = {"success", "constraint_failure", "invalid_output", "api_failure",
            "experiment_error", "interrupted"}
EVALUABLE = {"success", "constraint_failure", "invalid_output", "api_failure"}
PLANNING = {"success", "constraint_failure", "invalid_output"}


def average(values):
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def scenario_average(rows, measure):
    grouped = defaultdict(list)
    for row in rows:
        value = measure(row)
        if value is not None:
            grouped[row["scenario_id"]].append(value)
    return average([mean(values) for values in grouped.values()]), len(grouped)


def load_experiment(folder: Path):
    """Cross-check scheduled identities and state before trusting result rows."""
    manifest = json.loads((folder / "manifest.json").read_text())
    jobs = json.loads((folder / "schedule.json").read_text())
    states = json.loads((folder / "state.json").read_text())
    expected = {job["job_id"]: job for job in jobs}
    if len(expected) != len(jobs) or set(states) != set(expected):
        raise ValueError("duplicate schedule IDs or state/schedule mismatch")
    path = folder / "runs.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    seen = set()
    for row in rows:
        key = row["job_id"]
        if key in seen or key not in expected:
            raise ValueError("duplicate or unscheduled result: " + key)
        seen.add(key)
        if any(row[field] != expected[key][field] for field in
               ("scenario_id", "condition", "repetition")):
            raise ValueError("result identity mismatch: " + key)
        if row.get("dataset") != manifest["dataset"] or row.get("prompt_version") != manifest["prompt_version"]:
            raise ValueError("result dataset/prompt differs from manifest: " + key)
        if row["status"] not in TERMINAL or states[key] != row["status"]:
            raise ValueError("result/state mismatch: " + key)
    for key, status in states.items():
        if status in TERMINAL and key not in seen:
            raise ValueError("terminal state has no collected result: " + key)
        if status not in TERMINAL | {"pending", "running"}:
            raise ValueError("unknown job state: " + status)
    return manifest, jobs, states, rows


def condition_summary(condition, scheduled, rows):
    selected = [r for r in rows if r["condition"] == condition]
    valid = [r for r in selected if r["status"] in EVALUABLE]
    completed = [r for r in valid if r["status"] in PLANNING]
    success = [r for r in completed if r["status"] == "success"]
    result = {"condition": condition, "scheduled": scheduled, "recorded": len(selected),
              "evaluable": len(valid), "planning_completed": len(completed),
              "successes": len(success), "constraint_failures": sum(r["status"] == "constraint_failure" for r in selected),
              "invalid_outputs": sum(r["status"] == "invalid_output" for r in selected),
              "api_failures": sum(r["status"] == "api_failure" for r in selected)}
    measures = {
        "task_success_completed": (completed, lambda r: float(r["task_success"])),
        "task_delivery": (valid, lambda r: float(r["status"] == "success")),
        "completion_rate": (valid, lambda r: float(r["status"] in PLANNING)),
        "delivered_minimum": (valid, lambda r: r["delivered_minimum"]),
        "delivered_mean": (valid, lambda r: r["delivered_mean"]),
        "successful_minimum": (success, lambda r: r["delivered_minimum"]),
        "successful_mean": (success, lambda r: r["delivered_mean"]),
        "elapsed_seconds": (valid, lambda r: r["elapsed_seconds"]),
        "physical_requests": (valid, lambda r: r["usage"]["physical_requests"]),
        "logical_calls": (valid, lambda r: r["usage"]["logical_calls"]),
        "tokens_in": (valid, lambda r: r["usage"]["tokens_in"]),
        "tokens_out": (valid, lambda r: r["usage"]["tokens_out"]),
    }
    for name, (population, measure) in measures.items():
        result[name], result[name + "_scenarios"] = scenario_average(population, measure)
        result[name + "_jobs"] = sum(measure(r) is not None for r in population)
    return result


def paired_summary(rows, jobs):
    """Descriptive matched-scenario differences; no inference from a partial pilot."""
    grouped = defaultdict(list)
    scheduled = Counter((j["scenario_id"], j["condition"]) for j in jobs)
    for row in rows:
        if row["status"] in EVALUABLE:
            grouped[row["scenario_id"], row["condition"]].append(row)
    output = []
    for baseline, improved in (("A", "B"), ("B", "C2"), ("C0", "C2")):
        for metric in ("task_delivery", "delivered_minimum", "delivered_mean"):
            differences = []
            complete = 0
            for scenario in sorted({key[0] for key in grouped}):
                a, b = grouped.get((scenario, baseline), []), grouped.get((scenario, improved), [])
                if not a or not b:
                    continue
                def value(row):
                    return float(row["status"] == "success") if metric == "task_delivery" else row[metric]
                differences.append(mean(value(r) for r in b) - mean(value(r) for r in a))
                complete += len(a) == scheduled[scenario, baseline] and len(b) == scheduled[scenario, improved]
            output.append({"comparison": f"{improved}-{baseline}", "metric": metric,
                           "matched_scenarios": len(differences), "complete_matched_scenarios": complete,
                           "difference": average(differences), "wins": sum(d > 1e-12 for d in differences),
                           "ties": sum(abs(d) <= 1e-12 for d in differences),
                           "losses": sum(d < -1e-12 for d in differences),
                           "note": "descriptive only; repetitions may be incomplete; no confidence interval"})
    return output


def failure_rows(rows):
    counts = defaultdict(lambda: {"jobs": set(), "occurrences": 0})
    details = []
    for row in rows:
        report = row.get("report") or {}
        failures = list(report.get("violations", []))
        if report and report["hard_limit_satisfaction"] < 1:
            failures.append({"type": "hard_limit_failure", "detail": "one or more hard limits unmet"})
        if row["status"] in {"invalid_output", "api_failure", "experiment_error", "interrupted"}:
            failures.append({"type": row["status"], "detail": "see job artifact"})
        for failure in failures:
            item = counts[row["condition"], failure["type"]]
            item["jobs"].add(row["job_id"])
            item["occurrences"] += 1
            details.append({"job_id": row["job_id"], "condition": row["condition"],
                            "scenario_id": row["scenario_id"], "type": failure["type"],
                            "detail": failure["detail"],
                            "artifact": f"jobs/{row['job_id']}/result.json"})
    aggregate = [{"condition": condition, "type": kind, "affected_jobs": len(value["jobs"]),
                  "occurrences": value["occurrences"]}
                 for (condition, kind), value in sorted(counts.items())]
    return aggregate, details


def write_csv(path, rows):
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def display(value):
    return "—" if value is None else f"{value:.3f}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--output", type=Path, help="fresh analysis folder; defaults to experiment/analysis")
    args = parser.parse_args(argv)
    output = args.output or args.experiment / "analysis"
    if output.exists():
        parser.error("analysis folder exists; select a fresh --output to preserve reports")
    try:
        manifest, jobs, states, rows = load_experiment(args.experiment)
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    counts = Counter(states.values())
    summaries = [condition_summary(c, sum(j["condition"] == c for j in jobs), rows)
                 for c in manifest["conditions"]]
    pairs = paired_summary(rows, jobs)
    failures, detail = failure_rows(rows)
    invalid = counts["experiment_error"] > 0
    text = [f"# Planning results: {manifest['dataset']}", "",
            f"Recorded jobs: **{len(rows)}/{len(jobs)}**. Pending: **{counts['pending']}**. "
            f"Running: **{counts['running']}**. Interrupted: **{counts['interrupted']}**.", "",
            "**Experiment error present: do not publish performance conclusions.**" if invalid else
            "**Incomplete pilot: descriptive results only; no architecture ranking.**" if len(rows) != len(jobs) or counts["interrupted"] or counts["running"] else
            "Descriptive summary of recorded results; no statistical significance is established here.", "",
            "Rates and usage below average within each scenario first, then give scenarios equal weight. "
            "Missing conditions are unavailable, not zero. Completed-planning success excludes API failures; "
            "task delivery and delivered quality count API failures as no delivery. Conditional quality uses "
            "successful plans only and may compare different survivor sets.", "",
            "| Condition | Recorded/planned | Successful jobs | Completed-planning success | Task delivery | Delivered minimum | Requests/job | Seconds/job |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in summaries:
        text.append(f"| {row['condition']} | {row['recorded']}/{row['scheduled']} | {row['successes']} | "
                    f"{display(row['task_success_completed'])} | {display(row['task_delivery'])} | "
                    f"{display(row['delivered_minimum'])} | {display(row['physical_requests'])} | "
                    f"{display(row['elapsed_seconds'])} |")
    text += ["", "## Final failure types", "",
             "Counts are final-output failures, not all intermediate repair feedback. A job may have multiple types.", "",
             "| Condition | Failure | Affected jobs | Occurrences |", "| --- | --- | ---: | ---: |"]
    text += [f"| {r['condition']} | {r['type']} | {r['affected_jobs']} | {r['occurrences']} |" for r in failures]
    text += ["", "## Reading the artifacts", "",
             "`conditions.csv` includes each metric's job/scenario denominators. Token means exclude unknown "
             "usage and show their smaller denominators. `pairs.csv` contains descriptive matched-scenario "
             "differences and complete-pair counts; it supplies no confidence intervals. `failures.csv` links "
             "each final failure to its job result. `jobs.csv` lists every scheduled job, including pending jobs.", "",
             "This tool analyses one experiment only. Do not pool Kyoto/synthetic versions. A complete run "
             "still needs the protocol's paired uncertainty analysis, dependence checks, and qualitative review."]
    job_lookup = {r["job_id"]: r for r in rows}
    job_rows = [{**j, "status": states[j["job_id"]],
                 "elapsed_seconds": job_lookup.get(j["job_id"], {}).get("elapsed_seconds"),
                 "result_artifact": f"jobs/{j['job_id']}/result.json" if j["job_id"] in job_lookup else None}
                for j in jobs]
    output.mkdir(parents=True)
    for name, records in (("conditions", summaries), ("pairs", pairs), ("failure_counts", failures),
                          ("failures", detail), ("jobs", job_rows)):
        write_csv(output / f"{name}.csv", records)
    (output / "summary.json").write_text(json.dumps({"dataset": manifest["dataset"],
        "scheduled": len(jobs), "recorded": len(rows), "states": dict(counts),
        "experiment_error": invalid, "conditions": summaries, "pairs": pairs}, indent=2) + "\n")
    report = "\n".join(text) + "\n"
    (output / "summary.md").write_text(report)
    print(report)
    print(f"Saved offline analysis to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
