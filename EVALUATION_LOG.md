# Evaluation log

## Step 1 — local verification, 2 November 2026

- Purpose: verify implementation and Kyoto v2 development inputs before further model experiments.
- Base commit: `90c3704b8c4379d581ae47a6495a53f14b87fa87`.
- Working tree is not clean: evaluation documentation, summariser, runner snapshot update, pytest configuration, and summariser tests include uncommitted changes. The base commit alone does not identify the full checked implementation; commit reviewed changes before the final freeze. No commit was created by this check.
- Commands:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m scripts.validate_scenarios --scenarios data/scenarios_v2/dev
```

- Results: **214 tests passed**; one Google SDK/Python deprecation warning. **24 scenarios checked, zero invalid or unsolvable** under the validator's model.
- Evidence: [captured verification output](results/evaluation-checks-2026-11-02/verification.txt).
- Interpretation: local tests and the feasibility search pass. This does not establish LLM planning performance, real-world travel feasibility, or general security.
- Model/API usage: none for this step.

## Existing development pilot — reviewed 2 November 2026

- Dataset: `kyoto-v2-dev`; prompt version 3; configured model `gemini-3.5-flash-lite`.
- Existing artifacts: `results/kyoto-v2-pilot-01/`.
- Original command:

```bash
python -m tripbot.eval.run \
  --scenarios data/scenarios_v2/dev \
  --dataset kyoto-v2-dev \
  --output results/kyoto-v2-pilot-01 \
  --max-jobs 4
```

- Recorded: 4 of 288 scheduled jobs; 284 pending. One success and three constraint failures. Total physical requests recorded: 31. This entry does not represent a new model run.
- Conditions observed: two B jobs, one C0 job, one C2 job; no A. Scenarios/repetitions differ, so this is not a balanced architecture comparison.
- Evidence: [readable pilot summary](results/kyoto-v2-pilot-01/analysis/summary.md), [final failure details](results/kyoto-v2-pilot-01/analysis/failures.csv), and the per-job result/call artifacts.
- Observed repair behaviour: a budget correction can remove a required activity; restoring an activity can introduce budget or hard-limit failures. These are development observations, not final findings.

## Next step — matched development pilot (not started here)

- Use the same scenario `v2_dev_011` for A, B, C0, and C2, with three fresh generations each (12 jobs).
- Keep the existing pilot unchanged. Use a fresh experiment directory.
- No existing matched-pilot directory was present during this check.
- Before final evaluation, finish uncertainty analysis, decide/freeze new held-out data, and record the reviewed code revision.

## Evidence to explain to the professor at this stage

- The implemented checker is tested and the development scenarios admit valid plans under the simplified model.
- Every experiment saves inputs, configuration, source snapshots, model responses, request accounting, and failure statuses.
- The current pilot exposed real constraint-repair regressions; it does not establish an architecture winner.
- Main comparisons are A/B/C2, plus C0/C2 as a negotiation ablation. Synthetic diagnostics and Kyoto results remain separate.
- Final held-out results, uncertainty intervals, and final conclusions are still pending.


## Step 2 — matched development pilot, 3 November 2026

- Purpose: test A/B/C0/C2 on the same scenario before broader experiments.
- Input: Kyoto v2 development `v2_dev_011`, five friends; three fresh generations per condition (12 jobs).
- Model: `gemini-3.5-flash-lite`; prompt version 3; temperature 0; seed 42; caching disabled; maximum corrections 3.
- Code: base commit remains `90c3704b8c4379d581ae47a6495a53f14b87fa87` with uncommitted changes; the experiment manifest and source snapshot record the executed version.
- Initial attempt `results/kyoto-v2-matched-pilot-01/` hit sandbox connection errors: two API failures, one interrupted job, nine pending. It was stopped and preserved, not replaced or scored as planning failure.
- Network-enabled retry used a new folder:

```bash
.venv/bin/python -u -m tripbot.eval.run --scenarios data/scenarios_v2/dev/v2_dev_011.json --dataset kyoto-v2-dev-matched-pilot --output results/kyoto-v2-matched-pilot-02
.venv/bin/python -m tripbot.eval.summarise results/kyoto-v2-matched-pilot-02
```

- Completion: 12/12 recorded; no pending jobs or terminal API failures in the retry. **Task success: A 0/3, B 0/3, C0 0/3, C2 0/3.**
- Physical requests: A 3 total; B 12; C0 27; C2 57; total 99. Known usage: 480,738 input tokens, 21,630 output tokens. These are token counts, not monetary costs.
- Failure pattern: A/C0 over budget; B over budget and a hard-limit failure; C2 insufficient activities after reducing cost.
- Each condition produced one unique final plan across its three fresh requests. Do not treat these repetitions as independent scenarios.
- Recomputed every final report and repair-feedback list using archived input data: all matched. Separately rechecked the existing reference plan: cost 23, task success true, minimum satisfaction 0.5. This is evaluator consistency evidence; teammate independent review is still pending.
- Evidence: [readable summary](results/kyoto-v2-matched-pilot-02/analysis/summary.md), [pilot interpretation and reference table](results/kyoto-v2-matched-pilot-02/analysis/pilot_notes.md), [per-job recheck](results/kyoto-v2-matched-pilot-02/analysis/recheck.json), [reference plan](results/kyoto-v2-matched-pilot-02/analysis/reference_witness.json), plus manifest/source/input/call artifacts.
- Interpretation: the repair loops can trade one constraint failure for another. Additional computation did not deliver success on this one development case. This is not evidence of an overall architecture ranking.
- No prompt/model/data changes made after this pilot. Next decision: a small matched development sample covering contrasting conditions before considering revisions or final held-out design.


## Step 3 — varied matched development sample, selected 3 November 2026

Selection fixed before this batch: `data/eval_selections/dev-four-v1/selection.json`.
Byte-identical copies of Kyoto v2 development inputs are staged under its `dev/` directory; source data, prompts, model, and checker are unchanged.

- 001: two friends, mild direct conflict, tight budget.
- 002: same preferences/restrictions as 001, loose budget; matched budget comparison.
- 009: five friends, mild direct conflict, tight budget; avoids reusing previously inspected strong-conflict 011.
- 021: five friends, mild budget pressure, tight budget; a different mechanism. Contrasting 009/021 also changes preferences and actual budgets, so it cannot isolate mechanism causally.
- A/B/C0/C2 × 3 fresh generations × 4 cases = 48 jobs. At most 324 logical generation calls before retry multiplication; at most 1,296 physical requests if every logical call exhausts four attempts. Actual use will be reported.
- Purpose: diagnose whether development failures vary with group size and constraints, not establish a population-level architecture ranking.
- Output planned: `results/kyoto-v2-dev-four-01/`. Prior experiments remain separate. No new held-out data created.

```bash
.venv/bin/python -u -m tripbot.eval.run --scenarios data/eval_selections/dev-four-v1/dev --dataset kyoto-v2-dev-four-v1 --output results/kyoto-v2-dev-four-01
```


### Step 3 results — 3 November 2026

- All 48 jobs completed in `results/kyoto-v2-dev-four-01/`; no terminal API failures, interruptions, or pending jobs.
- Each condition succeeded 3/12 times (25%): all three generations passed for 002; all failed for 001, 009, and 021. This is a selected development sample, not a general estimate.
- Actual physical requests: 297; known input tokens 1,392,285; known output tokens 63,414. Mean requests/job: A 1, B 3.25, C0 6.75, C2 13.75. Mean elapsed seconds/job: A 1.423, B 4.900, C0 9.829, C2 19.399.
- Final failures: budget dominates; C0 on 001 ends with insufficient activities. All final hard limits satisfied in this batch. Each condition/scenario has one unique final plan across its three fresh requests.
- Rechecked 48 final reports and group repair-feedback lists against archived inputs: all match. Reference witnesses rechecked for all four scenarios: all valid. These are same-evaluator consistency checks; independent teammate manual review remains pending.
- Evidence: [readable summary](results/kyoto-v2-dev-four-01/analysis/summary.md), [case-by-case interpretation](results/kyoto-v2-dev-four-01/analysis/pilot_notes.md), [per-scenario table](results/kyoto-v2-dev-four-01/analysis/per_scenario.csv), [recheck results](results/kyoto-v2-dev-four-01/analysis/recheck.json), [reference witnesses](results/kyoto-v2-dev-four-01/analysis/reference_witnesses.json).
- Interpretation: additional checking/negotiation did not improve success on these cases. The controlled 001/002 pair suggests budget handling deserves investigation, but the small selected sample does not establish population-level effects or an overall architecture winner.
- No implementation/prompt/data changes made in response. Proposed next discussion: explicit effective group budget and whole-trip cost wording applied fairly across group planners; agree before editing. Preserve this baseline and avoid tuning on final held-out data.


## Step 4 — development prompt revision 4, 3 November 2026

- Approval: user agreed to change after discussing development versus final held-out evaluation.
- Motivation: repeated budget failures in v3 and correction regressions; this is development tuning, not final evaluation.
- Changes: identical computed minimum-group-budget and whole-trip arithmetic wording for A/B and C mediator; each friend agent receives its own limit only. B/C repairs receive prior computed total, effective group limit, and overage/headroom. All-constraint rechecking is explicit. Unknown/unparseable costs stay unknown.
- Unchanged: model/configuration, three architectures and C0/C2 settings, maximum corrections, datasets, schemas, checker/scoring, reference witnesses, and previous result artifacts.
- Implementation: `tripbot/planning/prompts.py`, `setup_b.py`, and `setup_c.py`.
- Verification: `.venv/bin/python -m pytest -q` → **221 passed**, one existing Google SDK/Python deprecation warning. Tests cover cross-day arithmetic, duplicate visit costs, unknown/malformed totals, equal group information, friend visibility, and actual B/C repair wiring. `git diff --check` passed.
- No live model calls for v4 yet; no claim of improvement. Preserve v3 as baseline; use a fresh, separately labelled output folder for the same four-case v4 development comparison. New held-out design/freeze remains pending.
- Explanation for professor: clearer budget representation is a shared development intervention, not a new architecture or relaxed criterion. Improved familiar-case scores, if observed, are development progress; generalisation requires untouched final cases.


## Step 5 — v4 matched development rerun, 3 November 2026

- Command:

```bash
.venv/bin/python -u -m tripbot.eval.run --scenarios data/eval_selections/dev-four-v1/dev --dataset kyoto-v2-dev-four-v1 --output results/kyoto-v2-dev-four-v4-01
.venv/bin/python -m tripbot.eval.summarise results/kyoto-v2-dev-four-v4-01
```

- All 48 jobs completed; no terminal API failures, pending jobs, or interruptions. Fresh responses, cache disabled, same scenario hashes/schedule/model settings as v3. Checker/schema source hashes also match. This is a development revision comparison, not final held-out testing.
- Success v3 → v4: A 3/12 → 3/12; B 3/12 → 3/12; C0 3/12 → 6/12; C2 3/12 → 3/12. The only success improvement is C0 case 009, 0/3 → 3/3. Each condition still succeeds on loose-budget case 002 and fails 001/021.
- V4 physical requests 294 (v3 297); known input/output tokens 1,409,280 / 60,708. Mean requests/job: A 1, B 3.25, C0 6.5, C2 13.75. No monetary cost is inferred from these counts.
- Remaining failures include B hard-limit regressions on 001/009 and a travel gap on 009; C0 activity-count failure on 021; budget violations elsewhere. Feasible plans that break hard limits still fail task success.
- All 48 reports and group repair-feedback lists match recomputation using archived inputs. Each scenario/condition yields one unique final plan over three fresh requests. Independent teammate review is still pending.
- Evidence: [v4 summary](results/kyoto-v2-dev-four-v4-01/analysis/summary.md), [version comparison](results/kyoto-v2-dev-four-v4-01/analysis/v3_vs_v4.csv), [interpretation and limitations](results/kyoto-v2-dev-four-v4-01/analysis/v3_vs_v4_notes.md), [recheck](results/kyoto-v2-dev-four-v4-01/analysis/recheck.json).
- Conclusion: limited development gain, not a general fix. Budget instructions and feedback changed together; the runs also occurred at different times. Preserve both versions. Next discussion: inspect representative repairs before deciding whether to retain bounded planning or introduce stronger constraint assistance. No further prompt changes or architecture additions made.
