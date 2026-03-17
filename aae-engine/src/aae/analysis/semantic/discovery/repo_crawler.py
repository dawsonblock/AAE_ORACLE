"""research_engine/discovery/repo_crawler — crawl GitHub repositories."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class RepoFile:
    """A single file discovered in a repository."""

    repo: str
    path: str
    url: str
    language: Optional[str] = None
    size_bytes: int = 0
    content: Optional[str] = None


@dataclass
class RepoCrawlResult:
    """Result of crawling a single GitHub repository."""

    repo: str
    files: List[RepoFile] = field(default_factory=list)
    readme: Optional[str] = None
    stars: int = 0
    topics: List[str] = field(default_factory=list)
    error: Optional[str] = None


class RepoCrawler:
    """Crawl GitHub repositories via the GitHub REST API.

    Parameters
    ----------
    token:
        Optional GitHub personal access token (avoids rate limits).
    max_files:
        Maximum number of files to retrieve per repository.
    file_extensions:
        Only retrieve files with these extensions.
    """

    _API = "https://api.github.com"

    def __init__(
        self,
        token: Optional[str] = None,
        max_files: int = 50,
        file_extensions: Optional[List[str]] = None,
    ) -> None:
        self._headers = {"Accept": "application/vnd.github+json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        self._max_files = max_files
        self._extensions = frozenset(
            file_extensions or [".py", ".md", ".yaml", ".toml", ".json"]
        )

    async def crawl(self, repo: str) -> RepoCrawlResult:
        """Crawl ``owner/repo`` and return a :class:`RepoCrawlResult`."""
        try:
            import httpx
            async with httpx.AsyncClient(
                headers=self._headers, timeout=20
            ) as client:
                meta = await self._get_meta(client, repo)
                tree = await self._get_tree(client, repo)
                readme = await self._get_readme(client, repo)
                files = await self._fetch_files(client, repo, tree)
            return RepoCrawlResult(
                repo=repo,
                files=files,
                readme=readme,
                stars=meta.get("stargazers_count", 0),
                topics=meta.get("topics", []),
            )
        except Exception as exc:
            log.warning("RepoCrawler failed for %s: %s", repo, exc)
            return RepoCrawlResult(repo=repo, error=str(exc))

    async def _get_meta(self, client, repo: str) -> dict:
        resp = await client.get(f"{self._API}/repos/{repo}")
        resp.raise_for_status()
        return resp.json()

    async def _get_tree(self, client, repo: str) -> List[dict]:
        resp = await client.get(
            f"{self._API}/repos/{repo}/git/trees/HEAD",
            params={"recursive": "1"},
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("tree", [])

    async def _get_readme(self, client, repo: str) -> Optional[str]:
        try:
            resp = await client.get(f"{self._API}/repos/{repo}/readme")
            if resp.status_code != 200:
                return None
            import base64
            return base64.b64decode(resp.json().get("content", "")).decode(
                "utf-8", errors="replace"
            )
        except Exception:
            return None

    async def _fetch_files(
        self, client, repo: str, tree: List[dict]
    ) -> List[RepoFile]:
        files = []
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            if not any(path.endswith(ext) for ext in self._extensions):
                continue
            if len(files) >= self._max_files:
                break
            raw_url = (
                f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"
            )
            content = await self._download(client, raw_url)
            ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
            files.append(
                RepoFile(
                    repo=repo,
                    path=path,
                    url=raw_url,
                    language=ext,
                    size_bytes=item.get("size", 0),
                    content=content,
                )
            )
        return files

    async def _download(self, client, url: str) -> Optional[str]:
        try:
            resp = await client.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return None
