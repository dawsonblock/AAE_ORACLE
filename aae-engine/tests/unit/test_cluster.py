"""tests/unit/test_cluster.py — unit tests for cluster + execution fabric."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# WorkerNode
# ---------------------------------------------------------------------------

class TestWorkerNode:
    def test_import(self):
        from aae.cluster.worker_node import WorkerNode
        assert WorkerNode is not None

    def test_instantiate(self):
        from aae.cluster.worker_node import WorkerNode

        async def _exec(task):
            return {"ok": True}

        node = WorkerNode(
            node_id="test-001",
            queue_name="test_queue",
            execute_fn=_exec,
            concurrency=1,
            worker_type="test",
        )
        assert node.node_id == "test-001"

    @pytest.mark.asyncio
    async def test_execute_task(self):
        from aae.cluster.worker_node import WorkerNode

        results = []

        async def _exec(task):
            results.append(task)
            return {"status": "done"}

        node = WorkerNode(
            node_id="test-002",
            queue_name="test_queue",
            execute_fn=_exec,
            concurrency=1,
            worker_type="test",
        )
        out = await node._execute_one({"task_id": "t1", "payload": {}})
        assert out["status"] == "done"
        assert len(results) == 1


# ---------------------------------------------------------------------------
# TaskDistributor (basic)
# ---------------------------------------------------------------------------

class TestTaskDistributor:
    def test_import(self):
        from aae.cluster.task_distributor import TaskDistributor
        assert TaskDistributor is not None

    def test_instantiate(self):
        from aae.cluster.task_distributor import TaskDistributor
        dist = TaskDistributor()
        assert dist is not None


# ---------------------------------------------------------------------------
# LoadBalancer
# ---------------------------------------------------------------------------

class TestLoadBalancer:
    def test_import(self):
        from aae.cluster.load_balancer import LoadBalancer
        assert LoadBalancer is not None

    def test_round_robin(self):
        from aae.cluster.load_balancer import LoadBalancer
        lb = LoadBalancer(strategy="round_robin")
        workers = ["w1", "w2", "w3"]
        selected = [lb.pick(workers) for _ in range(6)]
        # All workers should appear at least once
        assert set(selected) == {"w1", "w2", "w3"}

    def test_select_from_empty(self):
        from aae.cluster.load_balancer import LoadBalancer
        lb = LoadBalancer(strategy="round_robin")
        result = lb.pick([])
        assert result is None


# ---------------------------------------------------------------------------
# WorkerManager
# ---------------------------------------------------------------------------

class TestWorkerManager:
    def test_import(self):
        from aae.cluster.worker_manager import WorkerManager
        assert WorkerManager is not None

    def test_instantiate(self):
        from aae.cluster.worker_manager import WorkerManager
        mgr = WorkerManager()
        assert mgr is not None

    def test_register_and_list(self):
        from aae.cluster.worker_manager import WorkerManager
        mgr = WorkerManager()
        mgr.register("w1", {"type": "agent", "status": "idle"})
        mgr.register("w2", {"type": "sandbox", "status": "idle"})
        workers = mgr.list_workers()
        assert "w1" in workers
        assert "w2" in workers

    def test_deregister(self):
        from aae.cluster.worker_manager import WorkerManager
        mgr = WorkerManager()
        mgr.register("w3", {"type": "planner", "status": "idle"})
        mgr.deregister("w3")
        workers = mgr.list_workers()
        assert "w3" not in workers
