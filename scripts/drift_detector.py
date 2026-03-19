from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "aae-engine" / "src"
AAE_ROOT = ROOT / "aae"

LIVE_RUNTIME_DIRS = [
    AAE_ROOT / "analysis",
    AAE_ROOT / "code_analysis",
    AAE_ROOT / "dashboard_api",
    AAE_ROOT / "evaluation",
    AAE_ROOT / "execution",
    AAE_ROOT / "observability",
    AAE_ROOT / "oracle_bridge",
    AAE_ROOT / "planning",
    AAE_ROOT / "repair",
    AAE_ROOT / "runtime",
    AAE_ROOT / "storage",
]

FORBIDDEN_EXEC = [
    re.compile(r"\bsubprocess\.run\("),
    re.compile(r"\bexec\("),
]

ALLOWED_EXEC_FILES = {
    "sandbox_adapter.py",
    "coverage_runner.py",
}

FORBIDDEN_MODULES = [
    "aae.planner",
    "result_contracts",
]

REQUIRED_FILES = [
    "aae/execution/sandbox_adapter.py",
    "aae/repair/repair_loop.py",
    "aae/planning/planner.py",
    "aae/oracle_bridge/contracts.py",
    "aae/oracle_bridge/result_service.py",
]

FORBIDDEN_PATHS = [
    ROOT / "aae" / "planner",
    ROOT / "aae" / "oracle_bridge" / "result_contracts.py",
]


def iter_live_python_files() -> list[Path]:
    files: list[Path] = []
    for directory in LIVE_RUNTIME_DIRS:
        if directory.exists():
            files.extend(sorted(directory.rglob("*.py")))
    return files


def scan_execution() -> list[str]:
    issues: list[str] = []
    for path in iter_live_python_files():
        if path.name in ALLOWED_EXEC_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in FORBIDDEN_EXEC:
            if pattern.search(text):
                issues.append(f"Illegal execution in {path.relative_to(REPO_ROOT)}")
                break
    return issues


def scan_forbidden_modules() -> list[str]:
    issues: list[str] = []
    for path in iter_live_python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for module in FORBIDDEN_MODULES:
            if module in text:
                issues.append(f"Forbidden module reference '{module}' in {path.relative_to(REPO_ROOT)}")
    return issues


def check_required_files() -> list[str]:
    issues: list[str] = []
    for relative_path in REQUIRED_FILES:
        if not (ROOT / relative_path).exists():
            issues.append(f"Missing required file: {relative_path}")
    return issues


def check_forbidden_paths() -> list[str]:
    issues: list[str] = []
    for path in FORBIDDEN_PATHS:
        if path.is_dir():
            if any(path.rglob("*.py")):
                issues.append(f"Forbidden runtime path exists: {path.relative_to(REPO_ROOT)}")
            continue
        if path.exists():
            issues.append(f"Forbidden runtime path exists: {path.relative_to(REPO_ROOT)}")
    return issues


def main() -> None:
    issues: list[str] = []
    issues.extend(scan_execution())
    issues.extend(scan_forbidden_modules())
    issues.extend(check_required_files())
    issues.extend(check_forbidden_paths())

    if issues:
        print("\nDRIFT DETECTED:\n")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(1)

    print("No drift detected.")


if __name__ == "__main__":
    main()
