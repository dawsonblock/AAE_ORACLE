import re
from typing import Dict, List


class FailureLocalizer:
    _TRACE_RE = re.compile(r"(\S+\.py):(\d+)")

    def extract(self, text: str) -> List[Dict]:
        targets = []
        for line in text.splitlines():
            match = self._TRACE_RE.search(line)
            if match:
                targets.append(
                    {
                        "file": match.group(1),
                        "line": int(match.group(2)),
                        "confidence": 0.8,
                    }
                )
        return targets
