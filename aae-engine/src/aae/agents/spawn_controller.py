class SpawnController:
    def __init__(self, max_supervisors=5, max_workers_per_supervisor=8):
        """Manages hierarchical agent spawning with strict resource limits."""
        self.max_supervisors = max_supervisors
        self.max_workers_per_supervisor = max_workers_per_supervisor
        self.supervisors = {}  # {sid: {role: ...}}
        self.workers = {}      # {sid: [{id: ..., role: ...}]}

    def can_spawn_supervisor(self):
        """Global limit on supervisor count."""
        return len(self.supervisors) < self.max_supervisors

    def can_spawn_worker(self, supervisor_id):
        """Per-supervisor limit on concurrent worker agents."""
        worker_list = self.workers.get(supervisor_id, [])
        return len(worker_list) < self.max_workers_per_supervisor

    def register_supervisor(self, supervisor_id, role):
        """Adds supervisor to tracking list."""
        self.supervisors[supervisor_id] = {"role": role}

    def register_worker(self, supervisor_id, worker_id, role):
        """Adds worker to per-supervisor list."""
        self.workers.setdefault(supervisor_id, []).append({
            "id": worker_id, 
            "role": role
        })
