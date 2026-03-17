from __future__ import annotations

import importlib
import sys
from typing import Any, Dict, List, Optional


class DependencyLoader:
    """Lazy loader for optional runtime dependencies.

    Allows the system to start with minimal installed packages and load
    heavier dependencies (neo4j, qdrant, sentence-transformers, etc.)
    only when the feature that requires them is first used.
    """

    # Map: feature name → (import_path, pip_package)
    DEPENDENCY_MAP: Dict[str, tuple[str, str]] = {
        "redis": ("redis", "redis>=5.0"),
        "postgres": ("psycopg", "psycopg[binary]>=3.1"),
        "neo4j": ("neo4j", "neo4j>=5.0"),
        "qdrant": ("qdrant_client", "qdrant-client>=1.7"),
        "tree_sitter": ("tree_sitter", "tree-sitter>=0.21"),
        "sentence_transformers": ("sentence_transformers", "sentence-transformers>=2.6"),
        "numpy": ("numpy", "numpy>=1.26"),
        "sklearn": ("sklearn", "scikit-learn>=1.4"),
        "docker": ("docker", "docker>=7.0"),
        "prometheus": ("prometheus_client", "prometheus-client>=0.20"),
        "opentelemetry": ("opentelemetry.api", "opentelemetry-api>=1.23"),
        "beautifulsoup": ("bs4", "beautifulsoup4>=4.12"),
        "requests": ("requests", "requests>=2.31"),
        "boto3": ("boto3", "boto3>=1.34"),
        "networkx": ("networkx", "networkx>=3.0"),
    }

    def __init__(self) -> None:
        self._available: Dict[str, bool] = {}
        self._modules: Dict[str, Any] = {}

    def check(self, feature: str) -> bool:
        """Return True if the feature's backing package is importable."""
        if feature in self._available:
            return self._available[feature]
        import_path = self.DEPENDENCY_MAP.get(feature, (feature, feature))[0]
        try:
            importlib.import_module(import_path)
            self._available[feature] = True
        except ImportError:
            self._available[feature] = False
        return self._available[feature]

    def require(self, feature: str) -> Any:
        """Import and return a module, raising if not available."""
        if feature in self._modules:
            return self._modules[feature]
        import_path, pip_pkg = self.DEPENDENCY_MAP.get(
            feature, (feature, feature)
        )
        try:
            mod = importlib.import_module(import_path)
            self._modules[feature] = mod
            return mod
        except ImportError as exc:
            raise ImportError(
                "Feature '%s' requires '%s'. "
                "Install it with: pip install %s" % (feature, pip_pkg, pip_pkg)
            ) from exc

    def available_features(self) -> List[str]:
        """Return list of features that are currently importable."""
        return [f for f in self.DEPENDENCY_MAP if self.check(f)]

    def missing_features(self) -> List[str]:
        """Return list of features whose packages are not installed."""
        return [f for f in self.DEPENDENCY_MAP if not self.check(f)]

    def report(self) -> Dict[str, bool]:
        """Check all known features and return a status dict."""
        return {f: self.check(f) for f in self.DEPENDENCY_MAP}


# Module-level singleton
_loader: Optional[DependencyLoader] = None


def get_loader() -> DependencyLoader:
    global _loader
    if _loader is None:
        _loader = DependencyLoader()
    return _loader
