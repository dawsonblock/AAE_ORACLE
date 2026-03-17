class RootAgent:
    def __init__(self, spawn_controller, supervisor_factory):
        """Top-level agent overseeing the task tree and approvals."""
        self.spawn_controller = spawn_controller
        self.supervisor_factory = supervisor_factory

    def handle_goal(self, needed_roles):
        """Spawns root-level supervisors within global resource limits."""
        supervisors = []
        for role in needed_roles:
            if self.spawn_controller.can_spawn_supervisor():
                supervisor = self.supervisor_factory.create(role)
                self.spawn_controller.register_supervisor(
                    supervisor.supervisor_id, 
                    role
                )
                supervisors.append(supervisor)
        return supervisors

    def promote_candidate(self, candidate, result):
        """Rule 5: Final approval for fix promotion and PR creation."""
        # Verification checking happens here or within verifier.
        return result.get("verified", False)
