class SupervisorAgent:
    def __init__(self, supervisor_id, role, queue, event_bus):
        """Base for specific supervisors that decompose goals into tasks."""
        self.supervisor_id = supervisor_id
        self.role = role
        self.queue = queue
        self.event_bus = event_bus

    def decompose(self, goal):
        """Override to split root goals into discrete worker subtasks."""
        raise NotImplementedError

    def review(self, results):
        """Override to aggregate worker results and recommend fixes."""
        raise NotImplementedError
