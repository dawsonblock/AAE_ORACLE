"""security_analysis/dependency_scan/dependency_parser — parse manifests.

Reads ``requirements.txt``, ``pyproject.toml``, and ``package.json`` files
and returns normalised :class:`Dependency` records.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class Dependency:
    """A single declared dependency."""

    name: str
    version_spec: str = ""      # e.g. ">=1.2,<2.0"
    pinned_version: Optional[str] = None  # exact pin if available
    ecosystem: str = "pypi"     # "pypi" | "npm"
    source_file: str = ""


class DependencyParser:
    """Parse project manifests and return a flat list of :class:`Dependency`."""

    # ── requirements.txt ─────────────────────────────────────────────────────

    _REQ_LINE = re.compile(
        r"^\s*([A-Za-z0-9_.\-]+)"   # package name
        r"\s*([^#\n]*)"              # version specifier (optional)
    )
    _VER_PIN = re.compile(r"==\s*([^\s,;]+)")

    def parse_requirements_txt(self, path: Path) -> List[Dependency]:
        deps: List[Dependency] = []
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                m = self._REQ_LINE.match(line)
                if not m:
                    continue
                name = m.group(1)
                spec = m.group(2).strip().split("#")[0].strip()
                pin_m = self._VER_PIN.search(spec)
                deps.append(
                    Dependency(
                        name=name,
                        version_spec=spec,
                        pinned_version=pin_m.group(1) if pin_m else None,
                        ecosystem="pypi",
                        source_file=str(path),
                    )
                )
        except Exception as exc:
            log.warning("Failed to parse %s: %s", path, exc)
        return deps

    # ── pyproject.toml ───────────────────────────────────────────────────────

    def parse_pyproject_toml(self, path: Path) -> List[Dependency]:
        deps: List[Dependency] = []
        try:
            import tomllib  # type: ignore[import]
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[import,no-redef]
            except ImportError:
                log.warning("tomllib/tomli not available; skipping %s", path)
                return deps
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            sections: List[List[str]] = []
            # PEP 517 / setuptools
            proj = data.get("project", {})
            sections.append(proj.get("dependencies", []))
            for extras in proj.get("optional-dependencies", {}).values():
                sections.append(extras)
            # poetry
            poetry = data.get("tool", {}).get("poetry", {})
            sections.append(list(poetry.get("dependencies", {}).keys()))
            for spec_list in poetry.get("extras", {}).values():
                sections.append(spec_list)

            for section in sections:
                for raw in section:
                    m = self._REQ_LINE.match(raw)
                    if not m:
                        continue
                    name = m.group(1)
                    spec = m.group(2).strip()
                    pin_m = self._VER_PIN.search(spec)
                    deps.append(
                        Dependency(
                            name=name,
                            version_spec=spec,
                            pinned_version=pin_m.group(1) if pin_m else None,
                            ecosystem="pypi",
                            source_file=str(path),
                        )
                    )
        except Exception as exc:
            log.warning("Failed to parse %s: %s", path, exc)
        return deps

    # ── package.json ─────────────────────────────────────────────────────────

    def parse_package_json(self, path: Path) -> List[Dependency]:
        deps: List[Dependency] = []
        try:
            import json
            data = json.loads(path.read_text(encoding="utf-8"))
            for section in ("dependencies", "devDependencies"):
                for name, spec in data.get(section, {}).items():
                    pin_m = re.match(r"\^?~?(\d+\.\d+\.\d+)", spec)
                    deps.append(
                        Dependency(
                            name=name,
                            version_spec=spec,
                            pinned_version=pin_m.group(1) if pin_m else None,
                            ecosystem="npm",
                            source_file=str(path),
                        )
                    )
        except Exception as exc:
            log.warning("Failed to parse %s: %s", path, exc)
        return deps

    # ── unified entry point ───────────────────────────────────────────────────

    def parse_project(self, root: Path) -> List[Dependency]:
        """Auto-detect and parse all supported manifests under *root*."""
        deps: List[Dependency] = []
        for req in root.rglob("requirements*.txt"):
            deps.extend(self.parse_requirements_txt(req))
        for pp in root.rglob("pyproject.toml"):
            deps.extend(self.parse_pyproject_toml(pp))
        for pj in root.rglob("package.json"):
            if "node_modules" not in str(pj):
                deps.extend(self.parse_package_json(pj))
        return deps
