
import unittest
import uuid
import os
import shutil
import tempfile
from aae.events.schema import Event
from aae.events.event_store_simple import EventStore
from aae.events.event_bus_simple import EventBus
from aae.state.world_state import WorldState
from aae.agents.spawn_controller import SpawnController
from aae.agents.supervisor_factory import SupervisorFactory
from aae.agents.root_agent import RootAgent
from aae.execution.executor_simple import Executor
from aae.runtime.task_queue import TaskQueue

class TestEndToEndRepair(unittest.TestCase):
    def setUp(self):
        self.store = EventStore()
        self.bus = EventBus(self.store)
        self.state = WorldState()
        self.queue = TaskQueue()
        self.sc = SpawnController(max_supervisors=2, max_workers_per_supervisor=2)
        self.factory = SupervisorFactory(self.queue, self.bus, self.sc)
        self.root = RootAgent(self.sc, self.factory)
        
    def test_agent_hierarchy_spawning(self):
        """Tests that Root can spawn supervisors and they are tracked in state."""
        # 1. Root handles a goal by spawning supervisors
        roles = ["repair", "localization"]
        supervisors = self.root.handle_goal(roles)
        
        self.assertEqual(len(supervisors), 2)
        
        # 2. Verify tracking in SpawnController
        self.assertTrue("repair" in [s["role"] for s in self.sc.supervisors.values()])
        
        # 3. Simulate an event and apply to world state
        event_dict = self.bus.publish(
            "supervisor_spawned",
            "task-1",
            "repo-1",
            supervisors[0].supervisor_id,
            {"role": supervisors[0].role}
        )
        self.state.apply(event_dict)
        
        snapshot = self.state.snapshot()
        self.assertIn(supervisors[0].supervisor_id, snapshot["agent_tree"])

    def test_worker_decomposition(self):
        """Tests that RepairSupervisor can decompose a task into worker subtasks."""
        roles = ["repair"]
        supervisors = self.root.handle_goal(roles)
        repair_svc = supervisors[0]
        
        task = {
            "candidates": [
                {"command": {"type": "patch", "patch": "diff..."}, "mutation_type": "flip_condition"}
            ]
        }
        
        subtasks = repair_svc.decompose(task)
        self.assertEqual(len(subtasks), 1)
        self.assertTrue(subtasks[0]["worker_id"].startswith("worker-"))

if __name__ == "__main__":
    unittest.main()
