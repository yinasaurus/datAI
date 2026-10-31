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


The shared group objective (prompt version 3) is lexicographic: meet practical
constraints and every hard limit, then maximise minimum friend satisfaction,
then maximise equally weighted mean friend satisfaction. Satisfaction is distinct
liked-tag coverage, with no likes scoring 1. A higher mean cannot compensate for
a lower minimum. C's friend agents retain their advocacy role and limited profile
visibility; its mediator applies the same group objective as A/B. Repair prompts
retain that objective. Repair stopping still depends on constraint failures, not
proven satisfaction optimality; the objective is an instruction, not a guarantee.
