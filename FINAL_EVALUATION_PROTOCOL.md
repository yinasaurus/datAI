# Final held-out planning evaluation — frozen protocol

> Current status: Completed: 240/240 planning jobs at commit `46bf8d1e3c65ea8144e339eeb0f02d1577fae6d1` (method 7 / prompt 8). The original procedure below is retained as the preregistered design. Its pre-run pending/approval language is historical. No rerun or tuning is authorised.

No final model calls are authorised yet. Method v7 is retained; prompt v8 corrects shared constraint wording only. Final results must be labelled **method 7 / prompt 8**, separately from development versions. Commit this package and record the resulting Git revision before approving a full run. The runner's `--require-clean` enforces that freeze; manifests also preserve actual source hashes and source copies.

## Design and separation

Dataset: `data/final_eval_v1/heldout`, 20 new constructed scenarios, 10 template families with two budget variants each. All are feasible under the current checker. There are 8 straightforward, 8 conflicting and 4 highly constrained cases; group sizes 2/3/5 have 8/6/6 scenarios. Days vary 1–3. Budgets are in the existing catalogue's units, whole-trip attraction costs per person. No intentionally infeasible cases are included. Dataset family IDs, file hashes, world hashes and checker settings are in `data/final_eval_v1/manifest.json`.

A deterministic exact feasibility search produced `witnesses.json`; every witness independently passes `check_plan`, including all hard limits, and gives every friend positive satisfaction. These witnesses establish existence, not optimality. They must never be supplied to the planners. Preference/day structures were checked against existing scenario files and saved experiment inputs at generation time; these are new constructed profiles, not a random sample from a real population. Every profile has culture as one attainable shared interest, deliberately avoiding structurally zero minimum utility; this narrows generalisability.

The dataset uses the same Kyoto catalogue and constraint vocabulary as development: it tests unseen profiles and configurations, not unseen cities. Budget variants within a family are dependent. Inspecting checker witnesses is permitted for dataset validity; do not inspect model outputs, alter prompts or select scenarios using final model performance. Any post-freeze implementation change requires a new labelled experiment and disclosure; do not quietly rerun or overwrite failed jobs.

## Conditions and fixed settings

A: one planner generation. B: the same planner plus deterministic checking and at most three revisions. C0: one proposal per friend, mediator, same checking/revision loop. C2: initial friend proposals plus two negotiation rounds, mediator, same loop. C0 and C2 are ablations of C, not a fourth headline architecture. All conditions retain v7 shared eligibility filtering; B/C retain the existing cost-compatible repair assistance. Friend proposals remain private-profile prompts, while the mediator sees all profiles.

Prompt v8 uses the same explicit duration/opening-hours/travel-gap/budget/hard-restriction block for all group generation prompts. Exact days, no repeats, minimum two visits/day and global day windows remain specified. B inherits A's initial prompt. Friend-role and negotiation prompts are unchanged. No development-failure task optimisation is added.

Model: `gemini-3.5-flash-lite` as configured in config.yaml; temperature 0; requested seed 42; cache disabled; 3 repetitions per scenario/condition; schedule shuffled with seed 42. Total: **240 jobs**. Sequential execution, no optional stopping or architecture-dependent retry policy. SDK/service determinism and an immutable provider model version are not guaranteed. Logical retries: existing maximum four physical requests with recorded backoff. Unequal architecture call budgets are intentional; measure their costs rather than claim an equal-compute comparison.

## Outcomes and denominators

Within each scenario/condition, average repetitions first; architecture means then weight scenarios equally. Every CSV measure includes known job and scenario denominators. Do not present a partial run as the final experiment.

- Task success: checker feasibility AND hard-limit fraction = 1. `task_success_completed` excludes API failures but counts invalid JSON as failure. Primary end-to-end `task_delivery` counts API failures as zero; present both, with separate API/invalid-output/constraint counts.
- Feasibility: checker feasible indicator; invalid JSON = 0; API failures excluded.
- Hard-limit satisfaction: satisfied friend/rule instances / total applicable friend/rule instances; no hard rules = 1. Mean excludes missing checker reports; absent reports are never imputed as satisfied.
- Friend score: distinct liked tags covered / distinct liked tags; no likes = 1. Raw mean is the arithmetic mean across friends; raw minimum, max-minus-min gap and Jain index come from the checker even for constraint-failed plans. Jain = (sum scores)^2 / (n * sum squared scores); all-zero convention = 1. Raw means exclude absent reports and are diagnostic, not delivered performance.
- Delivered utility: each friend's raw score if task succeeds, otherwise zero for planning or API failure. `delivered_minimum` and `delivered_mean` summarise these utilities. Pending, interrupted and experiment-error jobs are unavailable, not failures with invented scores. Report raw gap/Jain separately; a zero-delivery group must not be interpreted as desirable fairness merely because all utilities are equal.
- Logical LLM calls and physical request counts include retries separately; input/output token means exclude unknown usage. Latency is wall-clock job time including retries/checking. Verification revisions count only trace steps named `revision`, not friend negotiation or total calls minus one; unavailable partial traces are not guessed.

All generated text, plans, reports and intermediate violations remain in per-job call logs and result traces. API failures are not planner constraint failures. A hard process kill may leave a job `running`; preserve and disclose it. No resume/overwrite is supported: interrupted batches need an explicitly labelled new batch, not silent replacement or selective reruns. Price estimates are not provided because no frozen price schedule is configured.

## Matched analysis

Prespecified comparisons: **B−A**, **C0−B**, **C2−C0**. Positive utility/success differences favour the second condition; lower calls/latency favour the cheaper condition. The primary outcomes are task delivery and delivered minimum; all other metrics are secondary descriptive outcomes. Conditional raw metrics require every repetition's value in both arms and disclose the smaller matched sample.

Each difference compares scenario-level repetition means. Compute 95% percentile bootstrap intervals using 1,000 draws, seed 42, resampling entire template families with replacement and retaining all their scenario variants. The point estimate weights scenarios equally; bootstrap means use all scenarios in sampled families. Repetitions and budget variants are never treated as independent sampling units. Intervals are only produced for fully collected evaluable batches with at least two labelled families. No p-values or multiplicity-corrected significance claims are made; intervals are marginal, exploratory uncertainty summaries over only 10 constructed families, not guarantees of population generalisation. Report all three prespecified contrasts, including null or negative findings.

## Commands

From repository root, with the existing virtual environment:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/validate_scenarios.py --scenarios data/final_eval_v1/heldout --config config.yaml
.venv/bin/python -m tripbot.eval.run --scenarios data/final_eval_v1/heldout --dataset kyoto-final-v1 --dataset-manifest data/final_eval_v1/manifest.json --split heldout --conditions A B C0 C2 --runs 3 --schedule-seed 42 --output results/kyoto-final-v1-dryrun-01 --dry-run
```

After the user approves the final run and the code freeze is committed:

```sh
.venv/bin/python -m tripbot.eval.run --scenarios data/final_eval_v1/heldout --dataset kyoto-final-v1 --dataset-manifest data/final_eval_v1/manifest.json --split heldout --conditions A B C0 C2 --runs 3 --schedule-seed 42 --output results/kyoto-final-v1-01 --require-clean
.venv/bin/python -m tripbot.eval.summarise results/kyoto-final-v1-01
```

Output directories must be fresh; choose a new suffix if one exists. The full command can make many paid requests; it has not been executed.

## Artifacts and report evidence

`manifest.json`: code revision/status/source hashes, prompt version, method version, configuration, package versions, dataset metadata/hashes and seed/retry policy. `source/`: captured source. `inputs/`: copied config, catalogue, travel, tags, scenarios and dataset manifest. `schedule.json` and `state.json`: job order and completion state. `runs.jsonl`: collected rows. `jobs/<id>/result.json`: plan/report/trace, usage and latency; `calls.jsonl` and `llm_log.jsonl`: prompts, responses, retries and errors. Startup failure produces `startup_error.json`.

Offline summary: `analysis/conditions.csv`, `pairs.csv` (differences/intervals/family counts), `failure_counts.csv`, `failures.csv`, `jobs.csv`, `summary.json`, `summary.md`. Preserve raw evidence and explain missing metrics. Show the professor the frozen design, dataset/witness checks, complete architecture table, three paired contrasts, error counts and representative final failure traces selected after reporting aggregate results.

Guardrail attack success and false-block evaluation are a separate experiment; this planning benchmark does not establish their effectiveness. Existing fixed catalogue opening hours, area-level travel estimates and tag-based preferences simplify real travel, and budgets omit broader trip expenses.
