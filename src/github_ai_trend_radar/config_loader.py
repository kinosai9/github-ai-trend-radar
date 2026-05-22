"""Configuration loading for github-ai-trend-radar."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration file must contain a mapping: {path}")
    return payload


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _normalize_topics(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    topics = payload.get("topics", payload)
    if isinstance(topics, list):
        normalized = {}
        for item in topics:
            if isinstance(item, dict) and item.get("name"):
                name = str(item["name"])
                normalized[name] = {key: value for key, value in item.items() if key != "name"}
        return normalized
    if isinstance(topics, dict):
        return {str(name): dict(config or {}) for name, config in topics.items()}
    raise ValueError("topics configuration must be a mapping or a list of named mappings")


def load_topics_config(
    config_dir: Path | str = "config",
    *,
    focus_topics: str | list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    root = Path(config_dir)
    payload = _read_yaml(root / "topics.default.yaml")
    local_payload = _read_yaml(root / "topics.local.yaml")
    if local_payload:
        payload = _merge_dicts(payload, local_payload)

    env_payload = os.getenv("TOPICS_JSON")
    if env_payload:
        parsed = json.loads(env_payload)
        if not isinstance(parsed, dict):
            raise ValueError("TOPICS_JSON must decode to a JSON object")
        payload = parsed

    topics = _normalize_topics(payload)
    selected = parse_focus_topics(focus_topics)
    if selected:
        missing = [name for name in selected if name not in topics]
        if missing:
            raise ValueError(f"Unknown focus topic(s): {', '.join(missing)}")
        topics = {name: topics[name] for name in selected}
    return topics


def parse_focus_topics(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item.strip() for item in value if item.strip()]
    return [item.strip() for item in value.split(",") if item.strip()]
