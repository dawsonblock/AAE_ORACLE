class RepoProfile:
    def __init__(self):
        self.mutation_stats = {}
        self.file_risk = {}
        self.failure_patterns = {}

    def update(self, payload):
        mutation_type = payload.get("mutation_type")
        file_path = payload.get("file")
        success = payload.get("success", False)
        pattern = payload.get("pattern")

        if mutation_type:
            self.mutation_stats.setdefault(mutation_type, 0)
            self.mutation_stats[mutation_type] += 1 if success else -1

        if file_path:
            self.file_risk.setdefault(file_path, 0)
            if not success:
                self.file_risk[file_path] += 1

        if pattern:
            self.failure_patterns.setdefault(pattern, 0)
            self.failure_patterns[pattern] += 1
