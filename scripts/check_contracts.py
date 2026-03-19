from __future__ import annotations

from pathlib import Path

CONTRACT_FILE = Path(__file__).resolve().parents[1] / "aae-engine" / "src" / "aae" / "oracle_bridge" / "contracts.py"

ALLOWED_SYMBOLS = {
    "PlanRequest",
    "Candidate",
    "ExperimentResultRequest",
    "ContractVersion",
    "CandidateType",
    "RiskLevel",
}


def main() -> None:
    text = CONTRACT_FILE.read_text(encoding="utf-8")

    bad: list[str] = []
    for line in text.splitlines():
        if line.startswith("class "):
            name = line.split()[1].split("(")[0].split(":")[0]
            if name not in ALLOWED_SYMBOLS:
                bad.append(name)

    if bad:
        print("Forbidden contract classes detected:", bad)
        raise SystemExit(1)

    print("Contracts clean.")


if __name__ == "__main__":
    main()
