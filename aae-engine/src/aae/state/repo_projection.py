class RepoProjection:
    def apply_all(self, events):
        repos = {}
        for e in events:
            repos.setdefault(e["repo_id"], []).append(e)
        return repos
