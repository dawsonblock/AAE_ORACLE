"""execution_fabric/worker_manager — fabric worker manager."""
from aae.cluster.worker_manager import WorkerManager as _Base


class FabricWorkerManager(_Base):
    """Alias of ``cluster.WorkerManager`` for the execution fabric."""
