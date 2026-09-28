"""Supabase Auth JWT verification (Stage 0 — see docs/STRATEGY.md sharing plan).

No FermentTrack users table: the Supabase JWT `sub` claim (works for both
anonymous and email sign-in) is used directly as `Culture.owner_id`. Verifies
the HS256 project JWT secret Supabase issues — no network call, no extra
service dependency.
"""

from __future__ import annotations

import jwt
from fastapi import Header, HTTPException

from fermenttrack.config import settings


async def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if not settings.supabase_jwt_secret:
        raise HTTPException(status_code=503, detail="Auth not configured")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated"
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    return payload["sub"]
