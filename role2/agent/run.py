"""Ask one question from the command line.

    python agent/run.py "Which orders are still shipped?"

Flags come from role2/.env. Override one for a single run by setting it first.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.answer import answer_question
from agent.config import load_config, resolve_log_path


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print('Usage: python agent/run.py "your question"', file=sys.stderr)
        return 2
    result = answer_question(question)
    print(result["answer"])
    print()
    print(f"success: {result['error'] is None}")
    print(f"attempts: {result['attempt_count']}")
    print(f"succeeded_attempt: {result['succeeded_attempt']}")
    print(f"row_count: {result['row_count']}")
    print(f"latency_ms: {result['latency_ms']}")
    print(f"tokens: {result['tokens']['total']}")
    print(f"log: {resolve_log_path(load_config())}")
    return 0 if result["error"] is None else 1


if __name__ == "__main__":
    sys.exit(main())
