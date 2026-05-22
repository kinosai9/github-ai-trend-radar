"""GitHub Repository API metadata and README collector."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"
README_LIMIT = 12000
DEFAULT_USER_AGENT = "github-ai-trend-radar/0.1 (+https://github.com/)"


class GitHubRepoClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        timeout: float = 20,
        retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.session = session or requests.Session()
        token = token or os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "User-Agent": DEFAULT_USER_AGENT,
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str, *, accept: str | None = None) -> requests.Response:
        url = f"{GITHUB_API_URL}{path}"
        headers = {"Accept": accept} if accept else None
        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout, headers=headers)
                if 400 <= response.status_code < 500:
                    response.raise_for_status()
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                response = getattr(exc, "response", None)
                if response is not None and 400 <= response.status_code < 500:
                    raise RuntimeError(f"GitHub API request failed for {path}: {exc}") from exc
                LOGGER.warning("GitHub API request failed on attempt %s/%s for %s: %s", attempt, self.retries, path, exc)
                if attempt < self.retries:
                    time.sleep(min(2 ** (attempt - 1), 5))

        raise RuntimeError(f"GitHub API request failed after {self.retries} attempts for {path}: {last_error}") from last_error

    def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        return self._get(f"/repos/{owner}/{repo}").json()

    def get_readme(self, owner: str, repo: str) -> str:
        try:
            response = self._get(
                f"/repos/{owner}/{repo}/readme",
                accept="application/vnd.github.raw",
            )
        except RuntimeError as exc:
            LOGGER.warning("README fetch failed for %s/%s: %s", owner, repo, exc)
            return ""

        return response.text[:README_LIMIT]
