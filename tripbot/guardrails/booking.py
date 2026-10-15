"""Mock booking. A human /confirm is the only way to set confirmed true."""

from __future__ import annotations

from typing import Any


def mock_book(plan: Any, confirmed: bool) -> dict[str, Any]:
    """Book only when ``confirmed`` is true. Otherwise leave the plan unbooked."""
    if confirmed is not True:
        return {"booked": False, "reason": "confirmed is false"}
    body = plan.model_dump() if hasattr(plan, "model_dump") else plan
    return {"booked": True, "plan": body}
