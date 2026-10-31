# Evaluation protocol — agreed design, not yet a frozen final experiment

This document records the agreed analysis rules established before the runner implementation.
It does not claim that experiments have run. Existing development fixtures may
be revised transparently; new held-out datasets have not been created or frozen.
The exact held-out design, sample counts, code revision, and model availability
must be recorded before final execution. Changes after inspecting final results
must be disclosed, versioned, and analysed separately.

## Questions and conditions

| Comparison | Question | Limit on interpretation |
| --- | --- | --- |
| A vs B | Does checker-guided revision help? | More calls are part of the intervention |
| B vs C | Does the per-friend/mediator architecture improve quality, at what resource cost? | Does not separate architecture from additional computation |
| C0 vs C2 | Do two extra proposal-exchange rounds help within C? | Includes the extra computation needed by those rounds |

There are three architectures only. C0 is C with `negotiation_rounds=0`; C2 uses
2 extra rounds and is the main C condition. Reuse the recorded C2 observations
for the ablation rather than running another condition labelled C2. No B-budget
or fourth architecture is included.

All conditions receive the same practical constraints and group objective:
meet feasibility and all hard limits, then maximise minimum friend satisfaction,
then equally weighted mean friend satisfaction. C retains its individual advocacy
roles and limited per-friend visibility. Current prompt version is 3. A is single
pass; B/C use up to 3 corrections. These differences are intentional.

## Datasets and boundaries

- Kyoto v2 development: pilot the runner and inspect planning behaviour. Legacy
  Kyoto scenarios remain documented stress cases; do not pool versions.
- Synthetic development: report controlled budget-choice diagnostics separately
  from Kyoto. Fictional costs are abstract units, not SGD. Reference audits never
  enter model prompts. Existing synthetic cases share a simple mechanism and are
  not independent samples of real traveller behaviour.
- New held-out sets: design after development decisions are settled, check their
  integrity/achievability, record provenance and hashes, and freeze before final
  model runs. Describe structural overlap with development, not merely file IDs.
- Profile extraction: evaluate labelled chats separately from planning. Main
  planning experiments use true scenario profiles, not tracker estimates.
- Security: report the mock tool-request harness, scripted enforcement tests, and
  actual bot-handler regression tests as separate evidence. Do not infer deployed
  security from a mock harness success rate.

## Execution

Use three fresh plan generations for every scenario × condition. Disable cache
reads and writes during measured calls, even if the ordinary bot config enables
caching. Save every response and trace as an artifact instead of regenerating it
for analysis. Three cached replays are not three observations.

Hold model ID, temperature (0), seed (42), dataset, checker, shared prompt version,
revision budget, and relevant config fixed across conditions. Fresh requests may
still return identical responses; report that rather than claiming independent
sampling merely because three requests were sent. Repetition measures observed
request-to-request stability under this fixed configuration.

Precompute a reproducible, interleaved order of scenario/repetition/condition jobs
using a recorded scheduling seed. Use the same scenario inputs across conditions;
do not run all A jobs on one day and all C jobs on another by design. Persist the
schedule. Run sequentially for interpretable latency unless concurrency is an
explicitly documented condition.

Keep the existing transient-error policy identical: at most four physical
requests per logical model call, exponential waits of 1, 2, and 4 seconds when
retryable. Account for requests and waits even on terminal failure. Do not replace
failed runs with successful reruns silently. Any subsequent rerun must remain
linked to the original attempt and reported separately. Internal retries are not
extra plan repetitions.

## Outcomes and failures

Every scheduled job needs a stable identifier and a result/status record.
Cancelled or never-started jobs remain visibly incomplete, not fabricated model
failures. Distinguish these terminal outcomes:

| Outcome | Task success | Overall delivered quality | Conditional plan analysis |
| --- | --- | --- | --- |
| Valid plan, feasible, all hard limits met | 1 | Actual minimum/mean satisfaction | Included in successful-plan quality |
| Valid plan failing feasibility or a hard limit | 0 | 0 | Keep raw checker scores and failure types separately |
| Invalid/unparseable model output after allowed repairs | 0 | 0 | No plan score; record invalid output |
| API failure after retry policy | Operational failure | 0 in end-to-end delivery metric | No invented plan/checker scores |
| Runner/checker defect | Experiment error | Do not publish a final score until resolved | Preserve evidence; invalidate affected experiment version |

"Overall delivered quality" is an evaluation convention: a plan that fails the
requirements earns zero usable quality even if a raw preference score is high.
It is not a claim about whether the Telegram bot literally sent a message.
Keep the raw checker report whenever a valid plan exists.

Report both task success among completed planning attempts (excluding API
failures) and end-to-end task delivery over all executed jobs (API failures count
as no delivery). Completion rate is the fraction of executed jobs ending with a
planning outcome rather than API failure. Always show denominators, operational
failure counts, and incomplete jobs. Do not interpret an API outage as evidence
of inferior planning reasoning.

## Metrics

Primary outcomes: task success and overall delivered minimum friend satisfaction.
Also show minimum satisfaction among task-successful plans, with its denominator.

Secondary outcomes: equally weighted mean satisfaction (overall delivered and
successful-plan conditional), feasibility, hard-limit satisfaction, invalid-output
rate, violation counts/types, satisfaction gap/Jain index, calls, tokens, and time.
Successful-plan conditional comparisons are descriptive: each setup may succeed
on different scenarios. Do not present differing survivor sets as a clean paired
causal comparison. Jain=1 with all-zero satisfaction does not mean useful quality.

Keep logical generation-call count separate from physical API-request count,
including retries. `PlanResult.llm_calls` alone does not measure physical requests.
Measure end-to-end elapsed time around the entire planning/checking job; keep
model-call timing separately. Save known token usage on partial failures. Missing
usage is unknown, not a measured zero. Report input/output tokens rather than
currency cost unless pricing has been sourced and documented for the chosen model.

For synthetic diagnostics, compare valid successful outputs to the reference
minimum optimum. Mean optimality is conditional on reaching the maximum minimum;
a higher mean with a lower minimum is not a better solution. Avoid collapsing the
lexicographic objective into an arbitrary weighted scalar.

## Aggregation and uncertainty

Within each dataset/version, average repetitions within each scenario first.
Give scenarios equal weight in aggregate summaries, then calculate paired
scenario-level differences for B−A, C2−B, and C2−C0. Report absolute scores,
differences, scenario wins/ties/losses, and sample sizes.

For Kyoto, use 1,000 paired bootstrap resamples of scenarios with a fixed recorded
seed, keeping all conditions/repetitions of a selected scenario together. Report
the 2.5th and 97.5th percentiles. These intervals describe this benchmark; they do
not establish population-wide traveller benefits. If the final dataset contains
multiple near-identical variants of one template, account for that dependence
(e.g. resample template families) and document the unit before freezing.

Do not treat three repetitions as three independent scenarios. Explain which
standard deviation describes across-scenario variation versus within-scenario
request variability. Use only prespecified difficulty slices, show their sizes,
and treat small slices or additional exploratory comparisons cautiously.

Use descriptive tables and worked examples for the small synthetic family;
no claim of statistical significance or generalisation from those fixtures.

## Qualitative analysis

Inspect every failed run and maintain a failure log with run IDs and evidence.
Use a written coding guide: timing/travel, budget, hard limits, unknown places,
missing/sparse/repeated visits, invalid structure, friend exclusion, mediator loss
of a proposed preference, and repair improvement/regression. Categories can overlap;
state whether counts represent runs or individual violations.

Select about five worked examples by declared categories: repair success, an
excluded friend, negotiation improvement/regression, extra cost without useful
improvement, and a security outcome. If a category does not occur, report that
instead of inventing an example. Include negative and tied outcomes. Use traces
to describe observable changes, not unverifiable claims about internal reasoning.
Have another teammate independently review a subset of checker judgements and
qualitative coding, reconcile disagreements, and document the process.

## Required artifacts and implementation gaps

Before final execution, save the protocol revision, code revision/dirty diff,
model/config, dataset/world identifiers and hashes, schedule, seeds, and retry
policy. Each result must link to scenario/condition/repetition IDs, terminal
status, plan/report if available, raw responses/traces, usage, timing, and errors.
Keep secrets out of artifacts and do not commit the canary in attack outputs.
Separate development, legacy, synthetic, and held-out outputs.

The planning runner is now implemented in `tripbot.eval.run`, with scoped logical
call observation and physical-request capture. It records responses, retry
attempts, partial known usage, terminal results, pending/interrupted states, and
source/input snapshots. Missing request usage is null, with known subtotals kept
separately. Normal bot calls do not enable the observer. Existing planner traces
still provide their original summaries; the per-job call artifacts preserve full
responses and intermediate prompts, including calls before terminal API failure.

The analysis pipeline, new held-out design/counts, and final freeze remain pending.
Runner tests use simulated responses and dry runs; implementation is not evidence
of model performance. No automatic resume or replacement of failed jobs is enabled.
