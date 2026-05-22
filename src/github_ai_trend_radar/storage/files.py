"""File storage helpers for snapshots and generated artifacts."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def ensure_directory(path: Path | str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def snapshot_path(
    snapshot_dir: Path | str,
    period: str,
    suffix: str,
    *,
    run_date: date | None = None,
) -> Path:
    day = run_date or date.today()
    return ensure_directory(snapshot_dir) / f"{day.isoformat()}-{period}-{suffix}.json"


def save_json(data: Any, path: Path | str) -> Path:
    target = Path(path)
    ensure_directory(target.parent)
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return target


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
