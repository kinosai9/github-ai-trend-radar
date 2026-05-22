"""JSON extraction helpers for model output."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_from_text(text: str) -> str:
    cleaned = (text or "").strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    if cleaned.startswith("{"):
        return cleaned

    start = cleaned.find("{")
    if start < 0:
        raise ValueError("No JSON object found in text")

    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(cleaned[start:], start=start):
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : index + 1]
    raise ValueError("Unclosed JSON object in text")


def parse_json_or_error(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(extract_json_from_text(text))
    except (ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "Parsed JSON is not an object"
    return payload, None
