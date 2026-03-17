import json


class StateEncoder:
    def encode(self, context):
        return json.dumps({
            "fail_count": context.get("fail_count", 0),
            "error_type": context.get("error_type", "unknown"),
            "files": len(context.get("files", [])),
            "coverage_gap": context.get("coverage_gap", 0),
            "recent_mutations": tuple(context.get("history", [])[-3:]),
            "active_supervisors": context.get("active_supervisors", 0),
            "worker_budget": context.get("worker_budget_remaining", 0),
        }, sort_keys=True)
