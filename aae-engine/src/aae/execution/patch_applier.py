from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict


class PatchApplier:
    def apply(self, file_path: str, new_code: str) -> Dict[str, str]:
        path = Path(file_path)
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy(path, backup)
        path.write_text(new_code, encoding="utf-8")
        return {"file_path": str(path), "backup_path": str(backup)}

    def rollback(self, file_path: str) -> None:
        path = Path(file_path)
        backup = path.with_suffix(path.suffix + ".bak")
        if backup.exists():
            shutil.copy(backup, path)
