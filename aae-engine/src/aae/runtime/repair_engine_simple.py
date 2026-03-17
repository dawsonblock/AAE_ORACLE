class RepairEngine:
    def __init__(self, planner, executor, evaluator):
        self.planner = planner
        self.executor = executor
        self.evaluator = evaluator

    def run(self, candidates, before_state):
        ranked = self.planner.plan(candidates)
        for candidate in ranked:
            result = self.executor.execute(candidate["command"])
            after_state = {
                "fail": 0 if result["verified"] else 1, 
                "patch_size": candidate.get("changes", 0)
            }
            evaluation = self.evaluator.evaluate(
                before_state, 
                after_state, 
                candidate.get("changes", 0)
            )
            if evaluation["success"]:
                return {"candidate": candidate, "evaluation": evaluation}
        return None
