"""Feed a saved chat into handle_message and print each reply."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from tripbot.bot.core import handle_message, load_state
from tripbot.config import load_config


def main(argv: list[str] | None = None) -> int:
    """Replay one JSON chat. Each item has ``sender`` and ``text``."""
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Replay a chat through handle_message")
    parser.add_argument("chat", type=Path, help="JSON list of {sender, text} messages")
    parser.add_argument("--group", default="replay")
    parser.add_argument("--override", action="append", default=[], metavar="key=value")
    args = parser.parse_args(argv)
    if not os.environ.get("GEMINI_API_KEY"):
        print("Put GEMINI_API_KEY in .env (copy .env.example).")
        return 1

    config = load_config(ROOT / "config.yaml", args.override)
    if config["model"] == "REPLACE_WITH_EXACT_MODEL_NAME":
        print("Set config.yaml model to the exact Gemini model id.")
        return 1
    messages = json.loads(args.chat.read_text(encoding="utf-8"))
    if isinstance(messages, dict):
        messages = messages["messages"]
    load_state(config)
    for message in messages:
        sender = str(message["sender"])
        text = str(message["text"])
        print(f"{sender}: {text}")
        reply = handle_message(args.group, sender, text, config)
        print("(no reply)" if reply is None else reply)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
