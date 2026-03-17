"""security_analysis/dependency_scan package."""
from .dependency_parser import Dependency, DependencyParser
from .vulnerability_db_client import ScanResult, Vulnerability, VulnerabilityDBClient

__all__ = [
    "DependencyParser",
    "Dependency",
    "VulnerabilityDBClient",
    "Vulnerability",
    "ScanResult",
]
