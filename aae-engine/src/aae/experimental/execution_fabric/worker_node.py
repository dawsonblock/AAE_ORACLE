"""execution_fabric/worker_node — fabric worker (re-uses cluster layer)."""
from aae.cluster.worker_node import WorkerNode as _Base


class FabricWorkerNode(_Base):
    """Alias of ``cluster.WorkerNode`` for the execution fabric."""
