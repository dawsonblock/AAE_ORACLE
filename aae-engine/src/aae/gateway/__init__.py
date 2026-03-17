"""Gateway subsystem — public-facing API surface for AAE.

Re-exports all gateway components for convenience.
"""
from .api_server import GatewayServer
from .auth_layer import AuthLayer
from .rate_limiter import RateLimiter
from .request_router import RequestRouter

__all__ = ["GatewayServer", "AuthLayer", "RateLimiter", "RequestRouter"]
