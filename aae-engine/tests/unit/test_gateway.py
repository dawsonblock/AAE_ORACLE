"""tests/unit/test_gateway.py — unit tests for gateway subsystem."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# AuthLayer
# ---------------------------------------------------------------------------

class TestAuthLayer:
    def test_import(self):
        from aae.gateway.auth_layer import AuthLayer
        assert AuthLayer is not None

    def test_valid_token(self):
        from aae.gateway.auth_layer import AuthLayer
        auth = AuthLayer(api_keys={"test-key-1": "user1"})
        assert auth.authenticate("test-key-1") == "user1"

    def test_invalid_token(self):
        from aae.gateway.auth_layer import AuthLayer
        auth = AuthLayer(api_keys={"valid-key": "user1"})
        result = auth.authenticate("bad-key")
        assert result is None

    def test_no_keys_configured(self):
        from aae.gateway.auth_layer import AuthLayer
        auth = AuthLayer(api_keys={})
        result = auth.authenticate("any-key")
        assert result is None


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_import(self):
        from aae.gateway.rate_limiter import RateLimiter
        assert RateLimiter is not None

    def test_allows_within_limit(self):
        from aae.gateway.rate_limiter import RateLimiter
        limiter = RateLimiter(rate=10, burst=10)
        for _ in range(5):
            allowed = limiter.check("client1")
        assert allowed is True

    def test_blocks_over_limit(self):
        from aae.gateway.rate_limiter import RateLimiter
        limiter = RateLimiter(rate=1, burst=1)
        # First request should pass
        limiter.check("client2")
        # Subsequent requests should be limited
        blocked = False
        for _ in range(20):
            if not limiter.check("client2"):
                blocked = True
                break
        assert blocked is True

    def test_separate_clients(self):
        from aae.gateway.rate_limiter import RateLimiter
        limiter = RateLimiter(rate=1, burst=1)
        # Each client has independent quota
        r1 = limiter.check("clientA")
        r2 = limiter.check("clientB")
        assert r1 is True
        assert r2 is True


# ---------------------------------------------------------------------------
# RequestRouter
# ---------------------------------------------------------------------------

class TestRequestRouter:
    def test_import(self):
        from aae.gateway.request_router import RequestRouter
        assert RequestRouter is not None

    def test_instantiate(self):
        from aae.gateway.request_router import RequestRouter
        router = RequestRouter()
        assert router is not None

    def test_register_and_route(self):
        from aae.gateway.request_router import RequestRouter
        router = RequestRouter()
        handler_called = []

        def handler(req):
            handler_called.append(req)
            return {"ok": True}

        router.register("/test", handler)
        result = router.route("/test", {"data": "value"})
        assert result == {"ok": True}
        assert len(handler_called) == 1

    def test_route_unknown(self):
        from aae.gateway.request_router import RequestRouter
        router = RequestRouter()
        result = router.route("/unknown", {})
        assert result is None or isinstance(result, dict)
