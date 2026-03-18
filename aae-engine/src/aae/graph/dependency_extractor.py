# Re-export from canonical location: aae.analysis.graph.dependency_extractor
from aae.analysis.graph.dependency_extractor import (
    module_name_from_path,
    normalize_import_name,
    is_python_test_path,
)

__all__ = ["module_name_from_path", "normalize_import_name", "is_python_test_path"]
