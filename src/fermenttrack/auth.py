"""Supabase Auth JWT verification (Stage 0 — see docs/STRATEGY.md sharing plan).

No FermentTrack users table: the Supabase JWT `sub` claim (works for both
anonymous and email sign-in) is used directly as `Culture.owner_id`.

The token header's `alg` picks one of two verifiers:
- HS256, legacy projects: the shared project JWT secret
  (`FERMENTTRACK_SUPABASE_JWT_SECRET`). No network call.
- ES256 / RS256, projects on JWT signing keys (the default for new ones): the
  public key whose `kid` matches the header, from
  `<FERMENTTRACK_SUPABASE_URL>/auth/v1/.well-known/jwks.json`. PyJWKClient
  caches the JWKS and refetches on an unknown `kid` (key rotation); the fetch
  runs in a worker thread, and a failed fetch is a 503 (auth server down, not a
  bad token).
Any other `alg` (including `none`) is a 401. Both require aud=authenticated,
`exp` and `sub`. 503 "Auth not configured" only when neither setting is set.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException
from starlette.concurrency import run_in_threadpool

from fermenttrack.config import settings

ASYMMETRIC_ALGS = ("ES256", "RS256")


@lru_cache(maxsize=1)
def _jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json", timeout=5)


def _decode(token: str, key: Any, algorithm: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        key,
        algorithms=[algorithm],
        audience="authenticated",
        options={"require": ["exp", "sub"]},
    )


async def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if not (settings.supabase_jwt_secret or settings.supabase_url):
        raise HTTPException(status_code=503, detail="Auth not configured")
    token = authorization.removeprefix("Bearer ")
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg == "HS256" and settings.supabase_jwt_secret:
            payload = _decode(token, settings.supabase_jwt_secret, "HS256")
        elif alg in ASYMMETRIC_ALGS and settings.supabase_url:
            client = _jwks_client(settings.supabase_url)
            try:
                jwk = await run_in_threadpool(client.get_signing_key_from_jwt, token)
            except jwt.PyJWKClientConnectionError:
                raise HTTPException(status_code=503, detail="Auth provider unreachable") from None
            # Verify with the JWK's own algorithm, not the header's: a header
            # claiming RS256 over an EC key's kid is then a clean 401.
            payload = _decode(token, jwk.key, jwk.algorithm_name)
        else:
            raise jwt.InvalidAlgorithmError(alg)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    return str(payload["sub"])


def is_admin(user_id: str) -> bool:
    """Read-only access to every account's data (FERMENTTRACK_ADMIN_USER_IDS)."""
    return user_id in {u.strip() for u in settings.admin_user_ids.split(",") if u.strip()}


async def require_admin(user_id: str = Depends(get_current_user_id)) -> str:  # noqa: B008
    if not is_admin(user_id):
        raise HTTPException(status_code=403, detail="Admins only")
    return user_id
