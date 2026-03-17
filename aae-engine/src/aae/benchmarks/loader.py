import json
import os
from pathlib import Path


class BenchmarkLoader:
    def __init__(self, cases_dir="benchmarks/cases"):
        self.cases_dir = Path(cases_dir)

    def load_all(self, language=None):
        """Loads all benchmark cases, optionally filtered by language."""
        cases = []
        if language:
            lang_dir = self.cases_dir / language
            if lang_dir.exists():
                cases.extend(self._load_from_dir(lang_dir))
        else:
            for lang_dir in self.cases_dir.iterdir():
                if lang_dir.is_dir():
                    cases.extend(self._load_from_dir(lang_dir))
        return cases

    def _load_from_dir(self, directory):
        """Loads all JSON benchmark files from a directory."""
        cases = []
        for file_path in directory.glob("*.json"):
            with open(file_path) as f:
                case_data = json.load(f)
                cases.append(case_data)
        return cases

    def get_case(self, case_id):
        """Retrieves a specific benchmark case by ID."""
        for case in self.load_all():
            if case.get("case_id") == case_id:
                return case
        return None
