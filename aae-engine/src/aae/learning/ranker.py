class AdaptiveRanker:
    def __init__(self):
        self.weights = {
            "mutation_score": 1.0,
            "file_risk": -0.2,
            "patch_size": -0.01,
            "files_modified": -0.5,
        }

    def score(self, features):
        return sum(weight * features.get(name, 0.0) for name, weight in self.weights.items())
