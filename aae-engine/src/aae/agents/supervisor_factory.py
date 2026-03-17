import uuid
from .localization_supervisor import LocalizationSupervisor
from .repair_supervisor import RepairSupervisor
from .test_supervisor import TestSupervisor
from .security_supervisor import SecuritySupervisor
from .regression_supervisor import RegressionSupervisor

class SupervisorFactory:
    def __init__(self, queue, event_bus, spawn_controller):
        self.queue = queue
        self.event_bus = event_bus
        self.spawn_controller = spawn_controller

    def create(self, role):
        sid = f"{role}-supervisor-{uuid.uuid4()}"
        mapping = {
            "localization": LocalizationSupervisor,
            "repair": RepairSupervisor,
            "test": TestSupervisor,
            "security": SecuritySupervisor,
            "regression": RegressionSupervisor,
        }
        return mapping[role](sid, self.queue, self.event_bus, self.spawn_controller)
