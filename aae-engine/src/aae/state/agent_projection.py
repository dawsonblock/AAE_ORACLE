class AgentTreeProjection:
    def apply_all(self, events):
        tree = {}
        for e in events:
            tree[e["agent_id"]] = {
                "parent_agent_id": e.get("parent_agent_id"),
                "type": e["type"],
                "payload": e["payload"],
            }
        return tree
