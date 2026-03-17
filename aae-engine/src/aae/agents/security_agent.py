from __future__ import annotations

from typing import Any, Dict, List

from aae.agents.base_agent import BaseAgent


class SecurityAgent(BaseAgent):
    """Autonomous security analysis agent.

    Dispatched by the controller for tasks of type ``security.*``.
    Interfaces with the Security Analysis Engine to detect vulnerabilities,
    score risks, and request remediation patches via APGS.
    """

    name = "security"
    domain = "security"

    async def run(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        action = task.get("action", "scan")
        if action == "scan":
            return await self.static_scan(task, context)
        if action == "dependency_audit":
            return await self.dependency_audit(task, context)
        if action == "attack_graph":
            return await self.build_attack_graph(task, context)
        if action == "remediate":
            return await self.remediate(task, context)
        return {"status": "unknown_action", "action": action}

    async def static_scan(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        repo_path = context.get("repo_path", ".")
        try:
            from aae.security_analysis.static_analysis.analyzer import SecurityAnalyzer
            analyzer = SecurityAnalyzer()
            findings = analyzer.scan(repo_path)
        except Exception as exc:
            findings = []
            context["security_scan_error"] = str(exc)

        return {
            "status": "scan_complete",
            "repo_path": repo_path,
            "finding_count": len(findings),
            "findings": findings[:20],    # cap for payload size
        }

    async def dependency_audit(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        repo_path = context.get("repo_path", ".")
        try:
            from aae.security_analysis.dependency_scan.dependency_parser import DependencyParser
            from aae.security_analysis.dependency_scan.vulnerability_db_client import VulnDBClient
            parser = DependencyParser()
            client = VulnDBClient()
            deps = parser.parse(repo_path)
            vulns = client.check_many(deps)
        except Exception as exc:
            deps, vulns = [], []
            context["dep_audit_error"] = str(exc)

        return {
            "status": "audit_complete",
            "dependency_count": len(deps),
            "vulnerable_count": len(vulns),
            "vulnerabilities": vulns,
        }

    async def build_attack_graph(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        repo_graph = context.get("repo_graph", {})
        try:
            from aae.security_analysis.attack_graph.attack_graph_builder import AttackGraphBuilder
            builder = AttackGraphBuilder()
            paths = builder.build(repo_graph)
        except Exception as exc:
            paths = []
            context["attack_graph_error"] = str(exc)

        return {
            "status": "graph_built",
            "attack_path_count": len(paths),
            "paths": paths[:10],
        }

    async def remediate(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        vulnerability = task.get("vulnerability", {})
        try:
            from aae.security_analysis.remediation.remediation_planner import RemediationPlanner
            planner = RemediationPlanner()
            plan = planner.plan(vulnerability)
        except Exception as exc:
            plan = {"error": str(exc)}

        return {
            "status": "remediation_planned",
            "vulnerability_type": vulnerability.get("type", "unknown"),
            "plan": plan,
        }
