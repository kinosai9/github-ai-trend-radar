"""Company profile loading for local research."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def load_company_profile(config_dir: str | Path = "config", *, profile: str = "enterprise_ai_service") -> dict[str, Any]:
    config_path = Path(config_dir)
    default_path = config_path / "company_profile.default.yaml"
    local_path = config_path / "company_profile.local.yaml"
    payload = _load_yaml(default_path)
    if local_path.exists():
        payload = _deep_merge(payload, _load_yaml(local_path))
    payload["profile"] = profile
    return payload


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
