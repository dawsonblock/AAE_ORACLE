"""gateway/auth_layer — lightweight authentication middleware.

Supports:
- Static API keys (for internal tooling)
- JWT bearer tokens (for human operators)
- No-auth mode for development

The layer is intentionally minimal — production deployments should put a
dedicated reverse proxy (nginx, Traefik) in front that handles TLS and
more complex AuthN/AuthZ.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Dict, Optional, Set

log = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when a request fails authentication."""


class AuthLayer:
    """Authenticate incoming requests via API key or JWT.

    Parameters
    ----------
    api_keys:
        Set of pre-shared API key strings.  An empty set means no-auth.
    jwt_secret:
        Optional secret for HS256 JWT verification.
    no_auth:
        If ``True``, all requests pass without checking credentials.
    """

    def __init__(
        self,
        api_keys: Set[str] | Dict[str, str] | None = None,
        jwt_secret: Optional[str] = None,
        no_auth: bool = False,
    ) -> None:
        # Support both a plain set of keys and a {key: identity} dict
        if isinstance(api_keys, dict):
            self._keys: Set[str] = set(api_keys.keys())
            self._key_identities: Dict[str, str] = dict(api_keys)
        else:
            self._keys = api_keys or set()
            self._key_identities = {}
        self._jwt_secret = jwt_secret
        self.no_auth = no_auth

    # ── public API ────────────────────────────────────────────────────────────

    def authenticate(
        self, token: Optional[str]
    ) -> Optional[Dict[str, str]]:
        """Validate *token* and return an identity dict (or ``None``).

        Returns ``{"sub": "<subject>", "type": "apikey"|"jwt"|"anon"}``
        on success, or ``None`` when credentials are invalid / missing.
        (Raises ``AuthError`` are caught internally.)
        """
        try:
            return self._authenticate_inner(token)
        except AuthError:
            return None

    def _authenticate_inner(
        self, token: Optional[str]
    ) -> Dict[str, str]:
        """Raise ``AuthError`` on failure (internal use)."""
        if self.no_auth:
            return {"sub": "anonymous", "type": "anon"}

        if not token:
            raise AuthError("No credentials provided.")

        # Strip 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        # Try API key first (constant-time compare)
        for key in self._keys:
            if hmac.compare_digest(
                token.encode(), key.encode()
            ):
                # If a {key: identity} mapping was provided, return identity
                identity = self._key_identities.get(key)
                if identity is not None:
                    return identity  # type: ignore[return-value]
                return {"sub": f"apikey:{_sha8(key)}", "type": "apikey"}  # type: ignore[return-value]

        # Try JWT
        if self._jwt_secret:
            return self._verify_jwt(token)

        raise AuthError("Invalid credentials.")

    def add_api_key(self, key: str) -> None:
        self._keys.add(key)

    def remove_api_key(self, key: str) -> bool:
        if key in self._keys:
            self._keys.discard(key)
            return True
        return False

    # ── JWT ───────────────────────────────────────────────────────────────────

    def _verify_jwt(self, token: str) -> Dict[str, str]:
        try:
            import jwt as pyjwt  # type: ignore[import]
            payload = pyjwt.decode(
                token,
                self._jwt_secret,
                algorithms=["HS256"],
                options={"require": ["sub", "exp"]},
            )
            exp = payload.get("exp", 0)
            if exp < time.time():
                raise AuthError("JWT expired.")
            return {
                "sub": str(payload.get("sub", "unknown")),
                "type": "jwt",
            }
        except ImportError:
            raise AuthError("PyJWT not installed; JWT auth unavailable.")
        except Exception as exc:
            raise AuthError(f"JWT verification failed: {exc}") from exc


def _sha8(key: str) -> str:
    """Return first 8 hex chars of SHA-256 (for logging, not crypto)."""
    return hashlib.sha256(key.encode()).hexdigest()[:8]
