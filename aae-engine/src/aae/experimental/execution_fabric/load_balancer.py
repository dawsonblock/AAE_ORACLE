"""execution_fabric/load_balancer — fabric load balancer."""
from aae.cluster.load_balancer import LoadBalancer as _Base


class FabricLoadBalancer(_Base):
    """Alias of ``cluster.LoadBalancer`` for the execution fabric."""
