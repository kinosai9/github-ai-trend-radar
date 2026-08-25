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
        self._token_candidates = _token_candidates(token)
        self._disabled_token_sources: set[str] = set()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "User-Agent": DEFAULT_USER_AGENT,
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _get(self, path: str, *, accept: str | None = None) -> requests.Response:
        url = f"{GITHUB_API_URL}{path}"
        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            active_tokens = [
                (token_source, token)
                for token_source, token in self._token_candidates
                if token_source not in self._disabled_token_sources
            ] or [("anonymous", "")]
            for token_source, token in active_tokens:
                headers = _headers_for_token(token, accept=accept)
                try:
                    response = self.session.get(url, timeout=self.timeout, headers=headers)
                    if _is_auth_failure_response(response) and token_source != self._token_candidates[-1][0]:
                        self._disabled_token_sources.add(token_source)
                        LOGGER.warning(
                            "GitHub API authentication failed with %s for %s; trying next credential source",
                            token_source,
                            path,
                        )
                        continue
                    if 400 <= response.status_code < 500:
                        response.raise_for_status()
                    response.raise_for_status()
                    return response
                except requests.RequestException as exc:
                    last_error = exc
                    response = getattr(exc, "response", None)
                    if response is not None and _is_auth_failure_response(response) and token_source != self._token_candidates[-1][0]:
                        self._disabled_token_sources.add(token_source)
                        LOGGER.warning(
                            "GitHub API authentication failed with %s for %s; trying next credential source",
                            token_source,
                            path,
                        )
                        continue
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


def _token_candidates(explicit_token: str | None = None) -> list[tuple[str, str]]:
    candidates = []
    if explicit_token:
        candidates.append(("explicit", explicit_token.strip()))
    candidates.extend(
        [
            ("GH_PAT", os.getenv("GH_PAT", "").strip()),
            ("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", "").strip()),
            ("anonymous", ""),
        ]
    )
    seen = set()
    unique = []
    for name, token in candidates:
        marker = token or name
        if marker in seen:
            continue
        seen.add(marker)
        unique.append((name, token))
    return unique


def _headers_for_token(token: str, *, accept: str | None = None) -> dict[str, str]:
    headers = {"Accept": accept} if accept else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _is_auth_failure_response(response: requests.Response) -> bool:
    if response.status_code not in (401, 403):
        return False
    try:
        payload = response.json()
    except ValueError:
        payload = {"text": response.text}
    message = str(payload.get("message") or payload.get("text") or "").lower()
    return any(token in message for token in ("bad credentials", "requires authentication", "resource not accessible"))
