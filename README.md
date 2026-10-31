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
