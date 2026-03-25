"""Git workflow helpers for the DeveloperAgent.

Provides clone → branch → agent work → commit → push → PR.

Requirements:
  - ``git`` on PATH
  - ``GITHUB_TOKEN`` env var for authenticated pushes and PR creation on GitHub
    (SSH-based repo URLs skip token injection and rely on the ssh-agent instead)
"""

from __future__ import annotations

import logging
import re
import subprocess

import httpx

log = logging.getLogger(__name__)


def _github_token() -> str:
    from conductor.config import settings  # lazy import to avoid pydantic at module load

    return settings.github_token


# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: str | None = None) -> str:
    """Run a shell command, raise RuntimeError on non-zero exit."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command {cmd} failed (exit {result.returncode}):\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clone_repo(repo_url: str, dest: str, branch: str) -> None:
    """Clone *repo_url* into *dest* and create+checkout *branch*.

    Uses a shallow clone (--depth=1) for speed.  If GITHUB_TOKEN is set and the
    URL is an HTTPS GitHub URL, the token is injected for authenticated access.
    """
    auth_url = _inject_token(repo_url, _github_token())
    _run(["git", "clone", "--depth=1", auth_url, dest])
    _run(["git", "checkout", "-b", branch], cwd=dest)
    log.info("Cloned %s → %s on branch %s", repo_url, dest, branch)


def commit_and_push(repo_path: str, branch: str, message: str) -> None:
    """Stage all changes, commit, and push *branch* to origin."""
    _run(["git", "add", "-A"], cwd=repo_path)
    # --allow-empty lets us push even when the agent made no file changes
    _run(["git", "commit", "--allow-empty", "-m", message], cwd=repo_path)
    _run(["git", "push", "origin", branch], cwd=repo_path)
    log.info("Pushed branch %s", branch)


async def open_pr(repo_url: str, branch: str, title: str, body: str) -> str:
    """Create a GitHub pull request and return its HTML URL.

    Raises ``RuntimeError`` if GITHUB_TOKEN is not set or the API call fails.
    """
    owner, repo = _parse_github_repo(repo_url)
    token = _github_token()
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set — cannot create a pull request. "
            "Set it in your .env file."
        )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"title": title, "head": branch, "base": "main", "body": body},
            timeout=30,
        )
        resp.raise_for_status()
    pr_url: str = resp.json()["html_url"]
    log.info("Opened PR: %s", pr_url)
    return pr_url


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _inject_token(repo_url: str, token: str) -> str:
    """Embed *token* into an HTTPS GitHub URL for authenticated cloning."""
    if not token:
        return repo_url
    if not repo_url.startswith("https://github.com"):
        return repo_url  # SSH URL — rely on ssh-agent
    return repo_url.replace("https://", f"https://x-access-token:{token}@")


def _parse_github_repo(repo_url: str) -> tuple[str, str]:
    """Extract ``(owner, repo)`` from a GitHub HTTPS or SSH URL."""
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
    if not match:
        raise ValueError(f"Cannot parse GitHub owner/repo from URL: {repo_url!r}")
    return match.group(1), match.group(2)
