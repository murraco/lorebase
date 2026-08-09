import base64
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from django.conf import settings

from sources.connectors.base import (
    Connector,
    ConnectorConfigError,
    ConnectorConnectionError,
    RawDocument,
)
from sources.connectors.registry import register_connector

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"
_MARKDOWN_SUFFIXES = (".md", ".markdown")
_REQUEST_TIMEOUT_SECONDS = 30


@register_connector("github")
class GitHubConnector(Connector):
    """Reads Markdown files, including READMEs, out of one or more GitHub
    repositories — authenticated with a personal access token, not OAuth,
    since this reads the token owner's own repos and there's no second
    party to authorize on behalf of.

    Change detection uses git's own blob SHA as `content_hash` rather than
    a hash computed here, unlike LocalFolderConnector: git already
    fingerprints every blob by content, so recomputing that would only be
    slower, never able to disagree with git if it tried.

    `config` keys:
      - `repos` (required): list of `"owner/name"` strings.
      - `branch` (optional): defaults to each repo's own default branch.
      - `path_prefixes` (optional): list of path prefixes: when given,
        only files under one of them are ingested.
    """

    def validate_config(self) -> None:
        repos = self.config.get("repos")
        if not repos or not isinstance(repos, list) or not all(isinstance(r, str) for r in repos):
            raise ConnectorConfigError(
                "config must include a non-empty 'repos' list of 'owner/name' strings"
            )
        for repo in repos:
            if repo.count("/") != 1:
                raise ConnectorConfigError(f"repo {repo!r} must be in 'owner/name' form")

        path_prefixes = self.config.get("path_prefixes")
        if path_prefixes is not None and (
            not isinstance(path_prefixes, list)
            or not all(isinstance(p, str) for p in path_prefixes)
        ):
            raise ConnectorConfigError("'path_prefixes', if given, must be a list of strings")

    def test_connection(self) -> None:
        for repo in self.config["repos"]:
            self._get(f"/repos/{repo}")

    def fetch_documents(self) -> Iterator[RawDocument]:
        path_prefixes = tuple(self.config.get("path_prefixes") or ())
        for repo in self.config["repos"]:
            branch = self.config.get("branch") or self._get(f"/repos/{repo}")["default_branch"]
            yield from self._fetch_repo(repo, branch, path_prefixes)

    def _fetch_repo(
        self, repo: str, branch: str, path_prefixes: tuple[str, ...]
    ) -> Iterator[RawDocument]:
        tree = self._get(f"/repos/{repo}/git/trees/{branch}", params={"recursive": "1"})
        if tree.get("truncated"):
            logger.warning(
                "Tree listing for %s@%s was truncated by the GitHub API; some files may be missing",
                repo,
                branch,
            )

        for entry in tree["tree"]:
            if entry["type"] != "blob":
                continue
            path = entry["path"]
            if not path.lower().endswith(_MARKDOWN_SUFFIXES):
                continue
            if path_prefixes and not path.startswith(path_prefixes):
                continue
            size = entry.get("size", 0)
            if size > settings.MAX_DOCUMENT_SIZE_BYTES:
                logger.warning(
                    "Skipping %s@%s: %d bytes exceeds MAX_DOCUMENT_SIZE_BYTES (%d)",
                    repo,
                    path,
                    size,
                    settings.MAX_DOCUMENT_SIZE_BYTES,
                )
                continue
            yield self._read_blob(repo, branch, path, entry["sha"])

    def _read_blob(self, repo: str, branch: str, path: str, blob_sha: str) -> RawDocument:
        blob = self._get(f"/repos/{repo}/git/blobs/{blob_sha}")
        content = base64.b64decode(blob["content"]).decode("utf-8")
        commit = self._last_commit(repo, branch, path)

        return RawDocument(
            external_id=f"{repo}@{path}",
            path=path,
            title=Path(path).stem,
            content_hash=blob_sha,
            content=content,
            metadata={
                "repo": repo,
                "branch": branch,
                "commit_sha": commit["sha"],
                "commit_author": commit["commit"]["author"]["name"],
                "commit_date": commit["commit"]["author"]["date"],
            },
        )

    def _last_commit(self, repo: str, branch: str, path: str) -> dict[str, Any]:
        # One request per file — the tree listing has no per-path commit
        # info, and the commits API has no bulk form. Fine at the scale a
        # personal notes repo lives at; a large monorepo would want this
        # cached or dropped, not fetched fresh on every sync.
        commits = self._get(
            f"/repos/{repo}/commits", params={"path": path, "sha": branch, "per_page": 1}
        )
        if not commits:
            # Only reachable via a force-push racing this request; nothing
            # real to attribute the blob to.
            return {"sha": "", "commit": {"author": {"name": "", "date": ""}}}
        result: dict[str, Any] = commits[0]
        return result

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

        try:
            response = requests.get(
                f"{_API_BASE}{path}",
                headers=headers,
                params=params,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise ConnectorConnectionError(f"GitHub API request failed: {exc}") from exc

        # A rate-limited response is still a 403/429 like any other
        # rejection, but "reauthenticate" and "wait until 14:32 UTC" call
        # for different actions — worth telling apart before it reaches
        # Source.last_error.
        if (
            response.status_code in (403, 429)
            and response.headers.get("X-RateLimit-Remaining") == "0"
        ):
            reset_header = response.headers.get("X-RateLimit-Reset")
            reset_at = (
                datetime.fromtimestamp(int(reset_header), tz=UTC).isoformat()
                if reset_header
                else "unknown time"
            )
            raise ConnectorConnectionError(f"GitHub API rate limit exceeded, resets at {reset_at}")

        if not response.ok:
            raise ConnectorConnectionError(
                f"GitHub API error for {path}: {response.status_code} {response.text[:200]}"
            )

        result: Any = response.json()
        return result
