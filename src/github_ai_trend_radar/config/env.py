"""Load local environment files for development."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_local_env(base_dir: Path | str | None = None) -> None:
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    for name in (".env", ".env.local"):
        load_dotenv(root / name, override=False)
