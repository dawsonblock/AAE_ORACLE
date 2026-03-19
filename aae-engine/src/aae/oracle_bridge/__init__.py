from .service import app
from .result_service import ResultService

__all__ = [
    "app",
    "ResultService",
]


def __getattr__(name: str):
    if name == "OraclePlanRequest":
        from .contracts import OraclePlanRequest

        return OraclePlanRequest
    if name == "OraclePlanningBridge":
        from .service import OraclePlanningBridge

        return OraclePlanningBridge
    raise AttributeError(name)
