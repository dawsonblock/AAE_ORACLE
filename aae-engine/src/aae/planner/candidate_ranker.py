class CandidateRanker:
    def score(self, candidate, learned_score=0):
        """Standard scoring including patch size penalty and learned weights."""
        score = 0
        # Penalize larger patches
        score -= candidate.get("changes", 0) * 0.001
        
        # Penalize complexity (file count)
        score -= candidate.get("files_modified", 1) * 0.5
        
        # Add feedback from per-repo learning layer
        score += learned_score
        return score
