"""execution_fabric/queue_adapter — fabric-specific queue (re-uses cluster layer)."""
from aae.cluster.queue_adapter import QueueAdapter as _Base


class FabricQueueAdapter(_Base):
    """Alias of ``cluster.QueueAdapter`` with fabric-specific defaults."""

    def __init__(self, redis_store=None):  # type: ignore[override]
        super().__init__(redis_store=redis_store)
