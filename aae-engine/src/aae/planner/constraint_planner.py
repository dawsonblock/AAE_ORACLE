from .candidate_filter import CandidateFilter
from .candidate_ranker import CandidateRanker

class ConstraintPlanner:
    def __init__(self):
        self.filterer = CandidateFilter()
        self.ranker = CandidateRanker()

    def plan(self, candidates, learned_scores=None):
        """Top-level planner: filters then ranks candidates."""
        learned_scores = learned_scores or {}
        
        # 1. Filter out invalid candidates
        filtered = self.filterer.filter(candidates)

        # 2. Sort by scores, including learned mutation-type modifiers
        ranked = sorted(
            filtered,
            key=lambda c: self.ranker.score(
                c, 
                learned_scores.get(c.get("mutation_type", "base"), 0)
            ),
            reverse=True
        )
        # 3. Return top 5 most promising candidates
        return ranked[:5]
