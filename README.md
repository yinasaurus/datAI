# tripbot

A Telegram bot that builds a trip plan for a group of friends whose preferences conflict. The study compares three planning setups (A, B, and C), sweeps settings, and scores every plan in code against ground truth. There is no user testing.

Read `PROJECT_SPEC.md` before changing a schema or a function contract. The model name lives in `config.yaml`. Secrets live in `.env`, never in code.

## Setup

Python 3.11 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
python -m pytest
```

Fill in `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `CANARY_TOKEN` in `.env`.

## Layout

`tripbot/` is the Python package. `load_config` in `tripbot/config.py` reads `config.yaml` and applies `key=value` overrides. Later modules will plan, check plans, guard actions, talk to Telegram, and run the experiments. Results, logs, and the LLM cache are gitignored.

## Current planning rules

Plans must contain exactly the requested days (numbered 1 through `days`), at
least two activities per day, and no repeated places across the trip. Configure
`days` and `min_activities_per_day` in `config.yaml`; scenario scripts use the
scenario's trip length. All setups receive these requirements and use the same
checker. B/C repair both feasibility failures and hard-limit failures, while
reporting those metrics separately.

Any group member may `/confirm` the latest plan. The bot rechecks it against
current profiles and planning rules, then applies the booking guard and budget
cap. Invalid plans are refused with an explanation. Booking is simulated.

On macOS, run the tests and bot from the repository root:

```bash
source .venv/bin/activate
python -m pytest -q
python -m tripbot.bot.telegram_app
```

Existing saved plans are revalidated under these rules at confirmation. Scores
from earlier rule or prompt versions should not be combined with new results.

## Profile corrections and unchecked requirements

State a correction explicitly, for example "remove hiking from my likes" or
"temples are fine now". Budgets are whole SGD per person for the entire itinerary.
`/profiles` shows the saved preferences and unchecked requirement categories.
Recognised slash commands do not make a profile-extraction API request.

The bot cannot verify dietary, accessibility, general availability, or other
unsupported requirements. It warns when these are detected. Dietary or
accessibility requirements pause planning and booking until each affected person
sends `/acknowledge` for their own requirements, or explicitly withdraws them.
Acknowledgement does **not** establish that the trip accommodates the requirement.
Repeating a requirement requires acknowledgement again.

Telegram profiles now use stable user IDs. On first live use, old name-based
profiles are archived and users need to share preferences again; the bot does not
infer ownership from matching names. Offline replay continues using sender names.
Extraction still depends on Gemini interpreting messages correctly; automated
unit tests use fake responses and do not establish real extraction accuracy.

## Development benchmark v2

The original scenarios are preserved. A new, unfrozen development-only draft is
in `data/scenarios_v2/dev`, with 24 scenarios, checker-verified witness plans,
and explicit satisfaction bounds. See [the benchmark notes](data/scenarios_v2/README.md)
for the design, limitations, and reproduction commands. No v2 held-out set exists.
The scenario validator now checks the configured activity minimum and prevents
repeated places across days; catalogue likes with no matching places are rejected.

## Separate synthetic development benchmark

`data/synthetic_v1/` contains eight clearly fictional budget-choice scenarios.
Each constrained case has individually achievable preferences, incompatible
full-group satisfaction, and several feasible compromises. Exhaustive audits
establish the reference minimum satisfaction and secondary mean scores. See
[the synthetic benchmark notes](data/synthetic_v1/README.md) for examples,
limitations, and commands. Use each world's matching `--config` when running
`scripts.run_setup_a` or `scripts.validate_scenarios`. Kyoto defaults are unchanged;
there is no synthetic held-out set yet.


The shared group objective (introduced in prompt version 3, retained in version 4) is lexicographic: meet practical
constraints and every hard limit, then maximise minimum friend satisfaction,
then maximise equally weighted mean friend satisfaction. Satisfaction is distinct
liked-tag coverage, with no likes scoring 1. A higher mean cannot compensate for
a lower minimum. C's friend agents retain their advocacy role and limited profile
visibility; its mediator applies the same group objective as A/B. Repair prompts
retain that objective. Repair stopping still depends on constraint failures, not
proven satisfaction optimality; the objective is an instruction, not a guarantee.

## Security enforcement and evaluation scope

The Telegram application requires `guardrails: "on"`. Offline mock attack
experiments may still switch guards off. When enabled, an unavailable, unfinished,
failing, or malformed guard blocks the action. Generated plan replies include
plan context for budget-cap enforcement; mock booking additionally rechecks the
plan against current profiles and requires a human `/confirm` command.

Cost checks reject unknown places, malformed plans, and empty itineraries rather
than treating them as free. Prices are loaded from the current data file.

`tripbot.eval.attacks` is a separate mock tool-request harness, not the normal
A/B/C planner. Its canary is planted in its own system prompt; ordinary planning
prompts do not contain that canary. The live reply filter still blocks the marker
if it appears in outgoing text. Canary and exact description-echo filtering are
limited checks, not proof of general prompt-injection resistance.

The final security runner is `tripbot.eval.security_v2`. The legacy `attacks` CLI
forwards to the archived V1 runner; both require a fresh `--output` directory. See
[final security V2 protocol](SECURITY_EVALUATION_PROTOCOL_V2.md) for exact commands,
independent action labels, metrics, security-only configuration and threat boundaries.
Its primary endpoint is counterfactual guard-boundary authorisation, not an actual
Telegram booking or configuration change. Model-driven, scripted-compromise and
scripted-control sources are reported separately. A model candidate is generated
once and replayed identically with guards off/on; caching is disabled.

Malformed output, API failure, model nonviolation and target-relevant guard blocking
have distinct labels. Primary attack success rates use valid attack outputs;
all-attempt rates and denominator/error counts are also reported. False-positive
rates use only independently safe reached actions in benign controls. Raw evidence
is owner-only under `private/`; public artifacts redact exact and obfuscated planted
canaries. The V2 development and held-out experiments are complete and frozen.

Security regression tests use simulated model responses and the actual bot
handler/guard path. No real Telegram delivery or Gemini attacks are implied by
passing these tests.

## Evaluation protocol

The [final planning protocol](FINAL_EVALUATION_PROTOCOL.md) defines the frozen A/B/C0/C2 experiment and family-aware analysis. The [final security protocol](SECURITY_EVALUATION_PROTOCOL_V2.md) defines the separate matched security experiment. Both studies are complete; their original pre-run approval language is historical, not permission to rerun.

Earlier protocols, development history and readiness checks are in [docs/archive](docs/archive/README.md). Keep them for traceability; use the final result CSVs for completed outcomes.

## Planning experiment runner

The runner executes A, B, C2, and C0 sequentially, with three fresh generations
per scenario by default. It forces caching off without changing the bot config.
Start with a dry run (no API requests):

```bash
.venv/bin/python -m tripbot.eval.run --scenarios data/scenarios_v2/dev --dataset kyoto-v2-dev --output results/kyoto-v2-dryrun --dry-run
```

For an actual development run, use a fresh output directory and omit `--dry-run`
(requires Gemini access and consumes API usage):

```bash
.venv/bin/python -m tripbot.eval.run --scenarios data/scenarios_v2/dev --dataset kyoto-v2-dev --output results/kyoto-v2-pilot --max-jobs 4
```

A cap executes only the shuffled prefix; remaining jobs stay pending. To select
just A/B/C without the ablation, use `--conditions A B C2`. For a synthetic world:

```bash
.venv/bin/python -m tripbot.eval.run --config data/synthetic_v1/n3/config.yaml --scenarios data/synthetic_v1/n3/dev --dataset synthetic-v1-n3-dev --output results/synthetic-n3-dryrun --dry-run
```

Always run from the repository root and use each world's matching config.
For held-out data, explicitly specify `--split heldout`; new held-out designs are
still pending. Never pool results solely because filenames or scenario IDs match.

Each experiment saves `manifest.json` (config, versions, input/source hashes),
`inputs/`, a relevant `source/` snapshot including uncommitted code,
`schedule.json`, and `state.json`. Per-job `result.json` and `calls.jsonl` retain
outcomes, plans/checker reports, prompts, raw model responses, and physical request
attempts. `runs.jsonl` collects terminal results. Successful usage is retained when
a later request fails; missing usage stays null with separate known subtotals.
Exception messages are omitted to avoid capturing credential-bearing URLs, and
known environment credentials are redacted from artifacts.

`experiment_error` stops execution for investigation. API failures are recorded
and execution continues. Interruptions are separate from model failures. A hard
process termination can leave a job marked running; do not treat it as completed.
Existing output directories are refused: automatic resume and silent reruns are
not implemented. Saved artifacts support offline analysis without new API calls;
the statistical analysis pipeline remains pending.

## Read experiment results without API calls

Generate an offline report from one saved experiment:

```bash
.venv/bin/python -m tripbot.eval.summarise results/kyoto-v2-pilot-01
```

Open `results/kyoto-v2-pilot-01/analysis/summary.md` for the readable table.
`conditions.csv` includes metric denominators; `failures.csv` links final failures
to jobs; `failure_counts.csv` distinguishes affected jobs from individual violations.
`jobs.csv` lists all scheduled jobs, including pending ones. `pairs.csv` shows
matched-scenario differences and complete-pair counts, descriptively only.
`summary.json` provides the corresponding machine-readable output.

An existing analysis folder is preserved. To regenerate into a new folder:

```bash
.venv/bin/python -m tripbot.eval.summarise results/kyoto-v2-pilot-01 --output results/kyoto-v2-pilot-01/analysis-02
```

Incomplete pilots cannot establish an architecture ranking. The summary averages
repetitions within scenarios before averaging scenarios, excludes unknown token
counts from token means with explicit denominators, and distinguishes API failures
from completed planning failures. It does not produce bootstrap intervals or
statistical significance claims; uncertainty analysis and qualitative review are
still required. `pytest.ini` restricts normal test discovery to `tests/`, keeping
archived source snapshots inside results from being collected as active tests.

## Development prompt revision 4

After v3 development pilots exposed repeated budget failures, v4 makes arithmetic
explicit for all architectures: whole-trip cost is the sum of every visit across
all days, and the shared group limit is the minimum individual budget. A/B and
C's mediator receive identical budget guidance; friend agents receive only their
own limit, without other profiles. Costs remain in each dataset's units.

B/C repairs receive the programmatically calculated prior total, limit, and
remaining/over-budget amount. Unknown IDs or unparseable plans have unknown total
rather than an invented zero. Repairs are reminded to preserve exact days,
activity minimum, uniqueness, timing/travel, and hard limits while fixing budget.
No schemas, scoring rules, revision allowances, datasets, or reference answers
changed. V3 results are preserved; do not combine them with v4 results as one
fixed-system experiment. V4 improvement has not yet been tested with live calls.

## Development feedback revision 5

V5 retains v4 budget guidance and makes B/C hard-limit repair feedback specific:
the affected friend, rule, offending day/place, and forbidden tag or actual versus
allowed start time. All offending visits are listed in one row per failed rule.
The normal report schema, feasibility/hard-limit separation, scores, datasets,
model, and revision allowance stay unchanged. This feedback revision is versioned
because it changes model inputs even though the base prompt wording is retained.

Local tests pass and all 48 stored v4 reports reproduce unchanged. No live v5
performance results exist yet. Retain v3/v4 runs separately; a v5 development run
must use a fresh output directory and is not final held-out evidence.

## Development method revision 6: shared candidate eligibility

At the public `make_plan` boundary, every architecture receives the same eligible
place catalogue computed from all friends' hard limits. Places carrying any
forbidden tag are excluded. A place is also excluded if its minimum duration
cannot fit between the group's earliest allowed start, its opening hours, and
the day end. Remaining places still need valid scheduled times and travel gaps.
No preferences, budget rankings, reference answers, or solver determine this list.

C's friend agents retain only their own raw profiles, but now receive the shared
group-derived eligible catalogue: this is an explicit shared preprocessing change,
not an identical information condition to v5. B/C repairs and the external checker
continue checking against the full dataset. Excluded known IDs remain known
places with hard-limit failures, rather than being relabelled hallucinations.

The first trace entry records `place_filter` metadata: version, original count,
eligible IDs, and excluded IDs/reasons. No source places/profiles/config are mutated,
and no invalid output is replaced with a reference plan. Empty eligibility is
visible in prompts/trace; the existing output validation still decides failure.

V6 is a method revision, not just a prompt wording change. Keep v3/v4/v5 results
separate. Local tests pass; no live v6 improvement has been measured yet. The
ordinary bot also uses this preprocessing through `make_plan`.

## Development method revision 7: cost-compatible repair options

B/C repairs now receive the same arithmetic-only candidate helper. For an
over-budget plan it lists eligible unused replacements whose single substitution
would bring the whole-trip total within the group budget. For an underfilled or
missing day it lists eligible unused additions affordable within the remaining
whole-trip budget. Entries include IDs, costs, resulting total, and affected day/
visit; options are ordered by cost then ID without preference ranking.

The model still chooses and schedules the itinerary. Candidates are **not**
certified timing/travel solutions and multiple options cannot be combined without
recalculating cost and avoiding repeated IDs. No single-edit option does not prove
infeasibility: coordinated changes may be necessary. Unknown/unparseable totals
receive no invented suggestions. The checker remains the final authority.

A remains single-pass with shared v6 eligibility. This is a documented expansion
of B/C's feedback harness, not a fourth architecture. Existing datasets, scores,
model settings, and revision limits are unchanged. Local tests pass. A six-job B/C development smoke passed all cases; this is
preliminary familiar-case evidence, not final generalisation. See the [archived development log](docs/archive/EVALUATION_LOG.md).

### Final held-out evaluation (completed and frozen)

Method v7 / prompt v8 completed all 240 planning jobs. A achieved 48/60 task successes; B, C0 and C2 each achieved 60/60. The separate security V2 held-out experiment completed 36 generations / 18 matched pairs; intended-target authorisation was 3/18 with guards off and 0/18 on. These bounded findings do not establish general architecture superiority or prompt-injection resistance.

Final metrics and paired intervals are in `results/kyoto-final-v1-01/analysis/conditions.csv` and `pairs.csv`. Security target outcomes and matched comparisons are in `results/security-v2-final-review-01/heldout_targets.csv` and `paired_outcomes.csv`. The protocols preserve pre-run decisions; their pending-approval language is historical. Do not rerun or tune frozen experiments.
