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


## Step 6 — inspect representative v4 repair histories, 3 November 2026

- Read-only inspection of C0/009/r1 (success), B/001/r1, and B/009/r1 (hard-limit failures). No live calls or application changes.
- C0/009: 25 → 25 → 23 by replacing p10 (8) with p07 (6); four valid visits, budget/hard limits/timing pass. Minimum satisfaction 0.5, mean 0.8. Saved travel gaps checked explicitly: 35/35 and 30/15 minutes actual/required.
- B/001: 32 → 18 (forbidden p12) → 28 → 22 (forbidden p12 again). Final feasibility true but task success false. Both raw preference scores are 1; this is not usable success because Ben forbids temples.
- B/009: 32 → 15 (forbidden p12) → 25 → 20 (forbidden p12 plus 25-minute gap where 40 required).
- Inspected budget feedback, hard-limit feedback, and stopping condition match the observed runs. No implementation bug identified in these paths. More specific offending-place feedback is a hypothesis for development improvement, not an implemented or proven fix.
- Evidence: [repair case studies and hand calculations](results/kyoto-v2-dev-four-v4-01/analysis/repair_case_studies.md).
- Next decision requires discussion: targeted hard-limit feedback for B/C versus a larger deterministic constraint-assistance intervention. No additional prompt revision, solver, filtering, or rerun performed.


## Step 7 — targeted hard-limit feedback revision 5, 3 November 2026

- User approved continuing with targeted feedback after discussing the controlled-testbed versus real-world scope.
- Changed only repair diagnostics/versioning: B and C share richer hard-limit messages naming the affected friend/rule and every offending day/place/tag or actual/earliest start time. Example from saved B/001: `Ben: no_temples; forbids tag temples; offending visits: day 2 p12 has forbidden tag temples`.
- One feedback row per failed friend/rule is retained. Unknown rules still raise; unknown place tags are not invented. The report schema, feasibility/hard-limit scoring, satisfaction metrics, source datasets, architectures, model settings, and repair allowance remain unchanged. Existing v4 budget guidance is retained.
- Verification: `.venv/bin/python -m pytest -q` → **228 passed**, one existing SDK/Python deprecation warning. Tests cover specific offending visits, multiple visits/friends, earliest-start boundaries, unknown places/rules, metric separation, and actual B/C repair prompts.
- Recomputed the 48 archived v4 final reports using the updated checker: **48/48 identical**. This establishes scoring consistency, not model performance improvement. Saved v4 feedback traces are historical and should not be expected to equal the newly expanded v5 diagnostic strings.
- No live API calls for v5. No prior artifacts changed. Application changes remain uncommitted after checkpoint `2b8aeb0`.
- Next: a version-separated development comparison if proceeding; final held-out design and independent teammate manual review remain pending. No stronger solver/filter or architecture added.


## Step 8 — v5 development test, 3 November 2026

```bash
.venv/bin/python -u -m tripbot.eval.run --scenarios data/eval_selections/dev-four-v1/dev --dataset kyoto-v2-dev-four-v1 --output results/kyoto-v2-dev-four-v5-01
.venv/bin/python -m tripbot.eval.summarise results/kyoto-v2-dev-four-v5-01
```

- Completed 48/48 jobs; no terminal API failures, interruptions, or pending jobs. Same input hashes and schedule as v4; model/settings/revision allowance unchanged. No changes during execution.
- Task success unchanged: A 3/12 (25%), B 3/12 (25%), C0 6/12 (50%), C2 3/12 (25%). No delivered-quality gain.
- B/001 changes across all three repetitions: v4 cost 22 with forbidden temple → v5 cost 27 with hard limit satisfied but over budget. B hard-limit failures decrease 6→3 jobs, over-budget failures increase 3→6. B/009 still breaks a hard limit and travel gap.
- 45/48 final plans and reports match v4 exactly. Rechecked all 48 v5 reports and group repair-feedback lists against archived inputs: all match. Repetition outputs remain identical within each scenario/condition; no independent-scenario or significance claim.
- Usage: 294 physical requests; known input/output tokens 1,409,388 / 60,708. No monetary cost inferred.
- Evidence: [v5 summary](results/kyoto-v2-dev-four-v5-01/analysis/summary.md), [comparison CSV](results/kyoto-v2-dev-four-v5-01/analysis/v4_vs_v5.csv), [interpretation](results/kyoto-v2-dev-four-v5-01/analysis/v4_vs_v5_notes.md), [recheck](results/kyoto-v2-dev-four-v5-01/analysis/recheck.json).
- Conclusion: more specific hard-limit feedback changes a failure mode without improving task success on this selected development sample. Preserve the negative result. Recommend pausing further paid prompt tweaks and discussing final system scope/version, independent manual review, held-out design, and analysis completion before final testing. No further architecture change or run authorised by this log entry.


## Step 9 — shared eligibility method revision 6, 3 November 2026

- User approved improving constraint handling; implemented the first scoped step, shared hard-limit filtering only. Replacement-cost assistance/solvers are not added.
- New `tripbot/planning/eligibility.py`: computes allowed IDs and exclusion reasons. All A/B/C callers through `make_plan` receive the same catalogue. Exclude globally forbidden tags and places with no allowed minimum-duration visit window; do not rank/filter by preferences or budget.
- C friend agents still see only their own raw profiles, but the common eligible catalogue incorporates group restrictions. This information change is explicit and applied fairly across architectures, not claimed identical to earlier v5 conditions.
- Full places remain available to checker/repair cost calculation, so hallucinated excluded IDs remain diagnosed as known-place hard-limit violations. Caller inputs/source data are not mutated, outputs are not replaced, and empty eligibility remains explicit. Trace records filter version, eligible IDs, and exclusions/reasons.
- Version incremented to 6 because this is a harness/method revision. Checker/scoring definitions, datasets, model settings, and repair allowances are unchanged; earlier versions/results preserved.
- Verification: `.venv/bin/python -m pytest -q` → **237 passed**, one existing SDK/Python deprecation warning. Tests cover shared actual A/B/C prompts including C negotiation, checking excluded IDs against the full dataset, exact earliest-start boundaries, input immutability, empty lists, unknown rules, and independence from likes/budget.
- Offline selection audit: 001/002/009 each retain 15 of 25 places and exclude p12; 021 retains all 25 because it has no forbidden category in its mild case. This does not solve its budget difficulty.
- No live v6 requests or performance claims yet. Next step: a small development pilot, with separate versioned artifacts, before considering further assistance. Changes remain uncommitted after checkpoint `2b8aeb0`.


## Step 10 — v6 small development pilot, 3 November 2026

- Prespecified selection: 001/009, A/B/C0/C2, one fresh generation each (eight jobs). Selection reasons and hashes saved in `data/eval_selections/v6-smoke-v1/selection.json`. Small diagnostic only; not comparable to a full 48-job average.

```bash
.venv/bin/python -u -m tripbot.eval.run --scenarios data/eval_selections/v6-smoke-v1/dev --dataset kyoto-v2-v6-smoke-v1 --runs 1 --output results/kyoto-v2-v6-smoke-01
.venv/bin/python -m tripbot.eval.summarise results/kyoto-v2-v6-smoke-01
```

- Completed eight/eight; no terminal API failures, interruptions, or pending jobs. Usage: 49 physical requests, known input/output tokens 167,580 / 10,738.
- Case 001: all conditions fail (A cost 28, B cost 26, C0/C2 three activities). Case 009: A/B/C0 pass at cost 23; C2 fails activity minimum. Every final hard limit passes.
- Same eight repetition-1 identities from v5: one success then versus three now; gains are A/B on 009. This is not an independent final sample or significance claim. The smoke job order differs from the larger v5 schedule.
- All eight final reports and group repair feedback match recomputation from saved inputs. Every captured prompt catalogue uses the intended same 15 IDs. The checker still uses the full original dataset.
- Evidence: [smoke interpretation](results/kyoto-v2-v6-smoke-01/analysis/pilot_notes.md), [summary](results/kyoto-v2-v6-smoke-01/analysis/summary.md), [matched repetition-1 comparison](results/kyoto-v2-v6-smoke-01/analysis/v5_vs_v6_smoke.csv), [recheck](results/kyoto-v2-v6-smoke-01/analysis/recheck.json).
- Interpretation: hard-limit filtering shows a limited gain on 009 but is not a general feasibility solution. Next discussion: replacement-cost assistance for B/C versus freezing the bounded methods. No added assistance, solver, or larger v6 rerun was performed.


## Step 11 — method revision 7, cost-compatible B/C repair options

- User approved arithmetic-only suggestions for replacements on over-budget plans and additions on underfilled days. Implemented shared `tripbot/planning/repair_options.py`; B/C both include its output through their existing budget feedback.
- Each option names an unused eligible place, its cost, the affected day/1-based visit for replacement, and resulting whole-trip cost. Candidates are sorted by cost/ID with no satisfaction ranking. The model must still choose and schedule.
- No automatic rewrite, solver, reference-plan fallback, budget change, or extra revision allowance. A stays single-pass with v6 eligibility. Scoring, datasets, model settings, and schemas unchanged; record this as a B/C harness intervention under version 7.
- Important limits: timing/travel and combined edits are not certified; options cannot be blindly combined. Empty one-edit lists do not establish infeasibility. Unknown/unparseable total cost receives no fabricated options.
- Verification: `.venv/bin/python -m pytest -q` → **244 passed**, one existing SDK/Python deprecation warning. Covers arithmetic, unused/eligible IDs, whole-trip budget, missing days, empty lists, unknown IDs, unchanged plans, timing caveats, and actual B/C feedback wiring.
- Offline example from saved v6 B/001: previous cost 26, replacing p19 (9) with eligible unused p07 (6) yields 23. This is a candidate cost calculation, not a new generated success or proof of a fully valid replacement schedule.
- No live v7 API requests. Earlier artifacts preserved. Next decision: small version-separated B/C development pilot before considering a full rerun; no new held-out set/freeze or automatic additional experiment in this entry.


## Step 12 — v7 B/C cost-assistance development smoke, 3 November 2026

- Prespecified cases 001/009, conditions B/C0/C2, one generation each (six jobs); A not run because this smoke targets repair assistance.

```bash
.venv/bin/python -u -m tripbot.eval.run --scenarios data/eval_selections/v6-smoke-v1/dev --dataset kyoto-v2-cost-assistance-smoke --conditions B C0 C2 --runs 1 --output results/kyoto-v2-v7-smoke-01
.venv/bin/python -m tripbot.eval.summarise results/kyoto-v2-v7-smoke-01
```

- **6/6 passed**, no terminal API failures, pending jobs, or interruptions. Every final plan costs 23, has minimum satisfaction 0.5, and passes timing/travel, hard limits, exact days, activity minimum, and uniqueness.
- Matched v6 repetition-1 identities: successes 2/6 → 6/6, requests 45 → 41. Development smoke only: different job orders/times, no fresh held-out evidence, no stable pass-rate estimate.
- V7 usage: 41 physical requests; known input/output tokens 140,872 / 8,934. B requests 2/1 for 001/009; C0 5/7; C2 9/17. No monetary cost inferred.
- Saved prompt/response inspection: B/001 uses offered p14 replacing p19 (28→23). C0/C2/001 first reduce 30→26 without a one-edit solution, then use offered p07 replacing p19 (26→23). This supports candidate use, not claims about internal reasoning. B/009 passes without repair. The decisive live repairs exercise replacements, not the addition feature.
- All six final reports and group repair-feedback lists match recomputation from saved inputs; each prompt uses the same intended 15-place eligible catalogue. Independent teammate manual review remains pending.
- Evidence: [pilot interpretation](results/kyoto-v2-v7-smoke-01/analysis/pilot_notes.md), [summary](results/kyoto-v2-v7-smoke-01/analysis/summary.md), [matched v6/v7 table](results/kyoto-v2-v7-smoke-01/analysis/v6_vs_v7.csv), [option-use observations](results/kyoto-v2-v7-smoke-01/analysis/repair_option_observations.json), [recheck](results/kyoto-v2-v7-smoke-01/analysis/recheck.json).
- No post-run prompt/code/data changes. Next decision: broader prespecified development coverage before choosing a final version and freezing untouched final evaluation; do not generalise six familiar-case successes to all trips.


## Step 13 — broader v7 development selection fixed before calls

Selected on 3 November 2026: 003 (two friends, strong direct conflict, tight), 007 (three friends, strong direct conflict, tight), 018 (three friends, mild budget pressure, loose control), 023 (five friends, strong budget pressure, tight/earliest-start limit). These files were not used in prior model runs, but are related development templates, not independent held-out evidence.

Selection reasons/hashes: `data/eval_selections/v7-broader-v1/selection.json`. Byte-identical source copies; no prompts, method, scoring, or model changes. A/B/C0/C2 once each, 16 jobs; all outcomes will be retained. Single generations cannot establish variability or generalisation. Planned output: `results/kyoto-v2-v7-broader-01/`.


### Step 13 results — broader v7 development check

```bash
.venv/bin/python -u -m tripbot.eval.run --scenarios data/eval_selections/v7-broader-v1/dev --dataset kyoto-v2-v7-broader-v1 --runs 1 --output results/kyoto-v2-v7-broader-01
.venv/bin/python -m tripbot.eval.summarise results/kyoto-v2-v7-broader-01
```

- All 16 jobs completed with no terminal API failures, interruptions, or pending jobs. No code/prompt changes during the run.
- Task success: A 1/4, B 4/4, C0 4/4, C2 3/4. Every final hard limit passes. C2's failure is case 023: day-2 p15→p13 has 30-minute gap versus 35 required. Retained as failure, without postprocessing correction.
- Mean delivered minimum satisfaction: A 0.125; B/C0 0.5833; C2 0.5. Mean requests/job: A 1; B 2.25; C0 5.75; C2 12.75.
- Usage: 87 physical requests; known input/output tokens 356,157 / 18,244. No monetary cost inferred.
- All sixteen final reports and group repair-feedback lists match recomputation using archived inputs. Independent teammate manual review remains pending.
- Evidence: [interpretation](results/kyoto-v2-v7-broader-01/analysis/pilot_notes.md), [summary](results/kyoto-v2-v7-broader-01/analysis/summary.md), [per-case CSV](results/kyoto-v2-v7-broader-01/analysis/per_scenario.csv), [recheck](results/kyoto-v2-v7-broader-01/analysis/recheck.json).
- These scenario IDs were not previously run, but share related development templates. One generation each is descriptive, not final held-out evidence or a stability estimate. Do not pool with earlier versions or synthetic cases.
- Interpretation: B/C0 succeed broadly in this selected sample with different resource use. A→B now measures the whole checker-guided cost-assisted repair harness, not checking alone. Extra C negotiation does not improve every case.
- Recommend pausing method changes and treating v7 as a final candidate pending independent review, checkpoint commit, completion of analysis/repetition decisions, and new held-out freeze. No freeze or further experiment automatically performed.
