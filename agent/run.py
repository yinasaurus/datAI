"""Ask one question from the command line.

    python agent/run.py "How many active students are there?"
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.loop import DEFAULT_LOG_PATH, ask


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print('Usage: python agent/run.py "your question"', file=sys.stderr)
        return 2
    run = ask(question)
    print(run.final_answer)
    print()
    print(f"success: {run.success}")
    print(f"attempts: {run.attempt_count}")
    if run.sql:
        print(f"sql: {run.sql}")
    print(f"log: {DEFAULT_LOG_PATH}")
    return 0 if run.success else 1


if __name__ == "__main__":
    sys.exit(main())
