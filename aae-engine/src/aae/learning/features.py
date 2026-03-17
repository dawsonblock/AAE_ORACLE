def extract_features(candidate, repo_profile):
    return {
        "mutation_score": repo_profile.mutation_stats.get(candidate["mutation_type"], 0),
        "file_risk": repo_profile.file_risk.get(candidate["file"], 0),
        "patch_size": candidate.get("changes", 0),
        "files_modified": candidate.get("files_modified", 1),
    }
