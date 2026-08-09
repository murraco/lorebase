import base64
import logging

import pytest
import requests
import responses
from responses import matchers

from sources.connectors.base import ConnectorConfigError, ConnectorConnectionError
from sources.connectors.github import GitHubConnector

_API = "https://api.github.com"


def _tree_url(repo: str, branch: str) -> str:
    return f"{_API}/repos/{repo}/git/trees/{branch}"


def _blob_url(repo: str, sha: str) -> str:
    return f"{_API}/repos/{repo}/git/blobs/{sha}"


def _mock_repo(repo: str, default_branch: str = "main") -> None:
    responses.add(responses.GET, f"{_API}/repos/{repo}", json={"default_branch": default_branch})


def _mock_tree(repo: str, branch: str, tree: list[dict], truncated: bool = False) -> None:
    responses.add(
        responses.GET,
        _tree_url(repo, branch),
        json={"sha": "tree-sha", "truncated": truncated, "tree": tree},
        match=[matchers.query_param_matcher({"recursive": "1"})],
    )


def _mock_blob(repo: str, sha: str, text: str) -> None:
    encoded = base64.b64encode(text.encode()).decode()
    responses.add(
        responses.GET,
        _blob_url(repo, sha),
        json={"sha": sha, "encoding": "base64", "content": encoded},
    )


def _mock_commit(repo: str, branch: str, path: str, sha: str, author: str, date: str) -> None:
    responses.add(
        responses.GET,
        f"{_API}/repos/{repo}/commits",
        json=[{"sha": sha, "commit": {"author": {"name": author, "date": date}}}],
        match=[matchers.query_param_matcher({"path": path, "sha": branch, "per_page": "1"})],
    )


def test_validate_config_requires_repos() -> None:
    connector = GitHubConnector({})

    with pytest.raises(ConnectorConfigError):
        connector.validate_config()


def test_validate_config_rejects_malformed_repo_names() -> None:
    connector = GitHubConnector({"repos": ["not-owner-slash-name"]})

    with pytest.raises(ConnectorConfigError):
        connector.validate_config()


def test_validate_config_rejects_non_list_path_prefixes() -> None:
    connector = GitHubConnector({"repos": ["octo/notes"], "path_prefixes": "docs/"})

    with pytest.raises(ConnectorConfigError):
        connector.validate_config()


def test_validate_config_accepts_well_formed_config() -> None:
    connector = GitHubConnector({"repos": ["octo/notes"], "path_prefixes": ["docs/"]})

    connector.validate_config()  # does not raise


@responses.activate
def test_test_connection_checks_every_configured_repo() -> None:
    _mock_repo("octo/notes")
    _mock_repo("octo/other")
    connector = GitHubConnector({"repos": ["octo/notes", "octo/other"]})

    connector.test_connection()  # does not raise

    assert len(responses.calls) == 2


@responses.activate
def test_test_connection_raises_on_unreachable_repo() -> None:
    responses.add(
        responses.GET, f"{_API}/repos/octo/missing", status=404, json={"message": "Not Found"}
    )
    connector = GitHubConnector({"repos": ["octo/missing"]})

    with pytest.raises(ConnectorConnectionError):
        connector.test_connection()


@responses.activate
def test_fetch_documents_reads_markdown_and_skips_everything_else() -> None:
    repo = "octo/notes"
    _mock_tree(
        repo,
        "main",
        [
            {"path": "README.md", "type": "blob", "sha": "sha-readme", "size": 8},
            {"path": "docs/guide.md", "type": "blob", "sha": "sha-guide", "size": 11},
            {"path": "docs", "type": "tree", "sha": "sha-docs-dir"},
            {"path": "image.png", "type": "blob", "sha": "sha-img", "size": 100},
            {"path": "notes.txt", "type": "blob", "sha": "sha-txt", "size": 5},
        ],
    )
    _mock_blob(repo, "sha-readme", "# Hello\n")
    _mock_blob(repo, "sha-guide", "Guide body.")
    _mock_commit(repo, "main", "README.md", "commit-1", "Ada", "2026-01-01T00:00:00Z")
    _mock_commit(repo, "main", "docs/guide.md", "commit-2", "Bo", "2026-02-02T00:00:00Z")

    connector = GitHubConnector({"repos": [repo], "branch": "main"})
    docs = {doc.external_id: doc for doc in connector.fetch_documents()}

    assert set(docs) == {"octo/notes@README.md", "octo/notes@docs/guide.md"}
    readme = docs["octo/notes@README.md"]
    assert readme.title == "README"
    assert readme.content == "# Hello\n"
    assert readme.content_hash == "sha-readme"
    assert readme.metadata == {
        "repo": repo,
        "branch": "main",
        "commit_sha": "commit-1",
        "commit_author": "Ada",
        "commit_date": "2026-01-01T00:00:00Z",
    }


@responses.activate
def test_fetch_documents_uses_repo_default_branch_when_not_configured() -> None:
    repo = "octo/notes"
    _mock_repo(repo, default_branch="trunk")
    _mock_tree(
        repo, "trunk", [{"path": "README.md", "type": "blob", "sha": "sha-readme", "size": 8}]
    )
    _mock_blob(repo, "sha-readme", "content")
    _mock_commit(repo, "trunk", "README.md", "commit-1", "Ada", "2026-01-01T00:00:00Z")

    connector = GitHubConnector({"repos": [repo]})
    (doc,) = list(connector.fetch_documents())

    assert doc.metadata["branch"] == "trunk"


@responses.activate
def test_fetch_documents_respects_path_prefixes() -> None:
    repo = "octo/notes"
    _mock_tree(
        repo,
        "main",
        [
            {"path": "README.md", "type": "blob", "sha": "sha-readme", "size": 8},
            {"path": "docs/guide.md", "type": "blob", "sha": "sha-guide", "size": 11},
        ],
    )
    _mock_blob(repo, "sha-guide", "Guide body.")
    _mock_commit(repo, "main", "docs/guide.md", "commit-2", "Bo", "2026-02-02T00:00:00Z")

    connector = GitHubConnector({"repos": [repo], "branch": "main", "path_prefixes": ["docs/"]})
    external_ids = {doc.external_id for doc in connector.fetch_documents()}

    assert external_ids == {"octo/notes@docs/guide.md"}


@responses.activate
def test_content_hash_is_the_git_blob_sha_not_a_computed_one() -> None:
    repo = "octo/notes"
    _mock_tree(repo, "main", [{"path": "a.md", "type": "blob", "sha": "sha-a", "size": 4}])
    _mock_blob(repo, "sha-a", "text")
    _mock_commit(repo, "main", "a.md", "c1", "Ada", "2026-01-01T00:00:00Z")

    connector = GitHubConnector({"repos": [repo], "branch": "main"})
    (doc,) = list(connector.fetch_documents())

    assert doc.content_hash == "sha-a"


@responses.activate
def test_oversized_blob_is_skipped_and_logged(settings, caplog: pytest.LogCaptureFixture) -> None:
    settings.MAX_DOCUMENT_SIZE_BYTES = 10
    repo = "octo/notes"
    _mock_tree(
        repo,
        "main",
        [
            {"path": "huge.md", "type": "blob", "sha": "sha-huge", "size": 999},
            {"path": "small.md", "type": "blob", "sha": "sha-small", "size": 4},
        ],
    )
    _mock_blob(repo, "sha-small", "ok")
    _mock_commit(repo, "main", "small.md", "c1", "Ada", "2026-01-01T00:00:00Z")

    connector = GitHubConnector({"repos": [repo], "branch": "main"})
    with caplog.at_level(logging.WARNING):
        external_ids = {doc.external_id for doc in connector.fetch_documents()}

    assert external_ids == {"octo/notes@small.md"}
    assert "huge.md" in caplog.text


@responses.activate
def test_truncated_tree_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    repo = "octo/notes"
    _mock_tree(repo, "main", [], truncated=True)

    connector = GitHubConnector({"repos": [repo], "branch": "main"})
    with caplog.at_level(logging.WARNING):
        list(connector.fetch_documents())

    assert "truncated" in caplog.text


@responses.activate
def test_rate_limit_raises_a_specific_error() -> None:
    responses.add(
        responses.GET,
        f"{_API}/repos/octo/notes",
        status=403,
        json={"message": "API rate limit exceeded"},
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
    )
    connector = GitHubConnector({"repos": ["octo/notes"]})

    with pytest.raises(ConnectorConnectionError, match="rate limit"):
        connector.test_connection()


@responses.activate
def test_request_includes_bearer_token_when_configured(settings) -> None:
    settings.GITHUB_TOKEN = "ghp_secret"
    _mock_repo("octo/notes")
    connector = GitHubConnector({"repos": ["octo/notes"]})

    connector.test_connection()

    assert responses.calls[0].request.headers["Authorization"] == "Bearer ghp_secret"


@responses.activate
def test_blob_with_no_commit_history_gets_empty_attribution() -> None:
    repo = "octo/notes"
    _mock_tree(repo, "main", [{"path": "a.md", "type": "blob", "sha": "sha-a", "size": 4}])
    _mock_blob(repo, "sha-a", "text")
    responses.add(
        responses.GET,
        f"{_API}/repos/{repo}/commits",
        json=[],
        match=[matchers.query_param_matcher({"path": "a.md", "sha": "main", "per_page": "1"})],
    )

    connector = GitHubConnector({"repos": [repo], "branch": "main"})
    (doc,) = list(connector.fetch_documents())

    assert doc.metadata["commit_sha"] == ""
    assert doc.metadata["commit_author"] == ""


@responses.activate
def test_network_failure_raises_connector_connection_error() -> None:
    responses.add(
        responses.GET, f"{_API}/repos/octo/notes", body=requests.exceptions.ConnectionError()
    )
    connector = GitHubConnector({"repos": ["octo/notes"]})

    with pytest.raises(ConnectorConnectionError, match="GitHub API request failed"):
        connector.test_connection()


@responses.activate
def test_request_omits_auth_header_when_no_token_configured(settings) -> None:
    settings.GITHUB_TOKEN = ""
    _mock_repo("octo/notes")
    connector = GitHubConnector({"repos": ["octo/notes"]})

    connector.test_connection()

    assert "Authorization" not in responses.calls[0].request.headers
