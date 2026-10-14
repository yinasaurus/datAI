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
