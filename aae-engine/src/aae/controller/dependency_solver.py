from __future__ import annotations

from typing import Dict, List, Optional, Set


class DependencySolver:
    """Topological solver for task dependency graphs.

    Given a mapping of task_id → list[dep_task_id], produces
    an ordered execution schedule respecting all dependency edges.
    Detects cycles and raises immediately so the controller never
    deadlocks on an unsatisfiable graph.
    """

    def __init__(self) -> None:
        self._graph: Dict[str, List[str]] = {}

    def add_task(self, task_id: str, dependencies: List[str]) -> None:
        """Register a task and its direct upstream dependencies."""
        self._graph[task_id] = list(dependencies)

    def remove_task(self, task_id: str) -> None:
        """Remove a completed or cancelled task from the solver."""
        self._graph.pop(task_id, None)
        for deps in self._graph.values():
            if task_id in deps:
                deps.remove(task_id)

    def ready_tasks(self, completed: Set[str]) -> List[str]:
        """Return all task IDs whose dependencies are fully satisfied."""
        return [
            task_id
            for task_id, deps in self._graph.items()
            if task_id not in completed and all(d in completed for d in deps)
        ]

    def resolve(self) -> List[str]:
        """Compute a full topological ordering of all registered tasks.

        Returns:
            Ordered list of task IDs (tasks earlier in list have no
            unsatisfied dependencies at the time they execute).

        Raises:
            ValueError: If the dependency graph contains a cycle.
        """
        in_degree: Dict[str, int] = {t: 0 for t in self._graph}
        adjacency: Dict[str, List[str]] = {t: [] for t in self._graph}

        for task_id, deps in self._graph.items():
            for dep in deps:
                if dep not in adjacency:
                    adjacency[dep] = []
                adjacency[dep].append(task_id)
                in_degree[task_id] += 1

        queue: List[str] = [t for t, d in in_degree.items() if d == 0]
        order: List[str] = []

        while queue:
            current = queue.pop(0)
            order.append(current)
            for dependent in adjacency.get(current, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(self._graph):
            remaining = set(self._graph) - set(order)
            raise ValueError(
                "Cycle detected in task dependency graph. "
                "Involved tasks: %s" % sorted(remaining)
            )

        return order

    def validate(self) -> Optional[str]:
        """Return an error description if the graph is invalid, else None."""
        try:
            self.resolve()
            return None
        except ValueError as exc:
            return str(exc)

    def subgraph(self, task_ids: List[str]) -> "DependencySolver":
        """Return a new solver containing only the specified tasks."""
        sub = DependencySolver()
        id_set = set(task_ids)
        for tid in task_ids:
            deps = [d for d in self._graph.get(tid, []) if d in id_set]
            sub.add_task(tid, deps)
        return sub
