"""get_current_user_id: HS256 (legacy secret) and ES256/RS256 via the project JWKS.

The JWKS is served by monkeypatching PyJWKClient.fetch_data, so the real
kid-lookup/caching code runs without network.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException
from jwt.algorithms import ECAlgorithm
from jwt.utils import base64url_encode

from fermenttrack import auth
from fermenttrack.config import settings

SUPABASE_URL = "https://example.supabase.co"
KID = "test-kid"
SECRET = "legacy-hs256-secret-at-least-32-bytes!"
EC_KEY = ec.generate_private_key(ec.SECP256R1())


def _claims(**overrides: Any) -> dict[str, Any]:
    return {"sub": "user-123", "aud": "authenticated", "exp": int(time.time()) + 3600, **overrides}


def _es256(kid: str = KID, key: Any = EC_KEY, **claims: Any) -> str:
    return jwt.encode(_claims(**claims), key, algorithm="ES256", headers={"kid": kid})


async def _user(token: str) -> str:
    return await auth.get_current_user_id(f"Bearer {token}")


async def _status(token: str) -> int:
    with pytest.raises(HTTPException) as exc:
        await _user(token)
    return exc.value.status_code


@pytest.fixture
def jwks(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """JWKS-only config, serving EC_KEY's public JWK under KID."""
    jwk = ECAlgorithm.to_jwk(EC_KEY.public_key(), as_dict=True) | {"kid": KID, "alg": "ES256"}
    monkeypatch.setattr(settings, "supabase_url", SUPABASE_URL)
    monkeypatch.setattr(settings, "supabase_jwt_secret", None)
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: {"keys": [jwk]})
    auth._jwks_client.cache_clear()
    yield
    auth._jwks_client.cache_clear()


async def test_es256_token_is_accepted(jwks: None) -> None:
    assert await _user(_es256()) == "user-123"


async def test_jwks_url_is_derived_from_project_url(jwks: None) -> None:
    await _user(_es256())
    client = auth._jwks_client(SUPABASE_URL)
    assert client.uri == f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda: _es256(aud="anon"), id="wrong-audience"),
        pytest.param(lambda: _es256(exp=int(time.time()) - 60), id="expired"),
        pytest.param(lambda: _es256(kid="rotated-away"), id="unknown-kid"),
        pytest.param(
            lambda: _es256(key=ec.generate_private_key(ec.SECP256R1())), id="signed-by-other-key"
        ),
        pytest.param(lambda: jwt.encode(_claims(), None, algorithm="none"), id="alg-none"),
        pytest.param(
            lambda: jwt.encode(_claims(), None, algorithm="none", headers={"kid": KID}),
            id="alg-none-with-kid",
        ),
        # Header says RS256 but the kid is the EC key: verified with the JWK's
        # own algorithm, so this is a mismatch, not a 500 from key-type errors.
        pytest.param(
            lambda: jwt.encode(
                _claims(),
                rsa.generate_private_key(public_exponent=65537, key_size=2048),
                algorithm="RS256",
                headers={"kid": KID},
            ),
            id="rs256-header-on-ec-kid",
        ),
        # A valid-looking HS256 token when only JWKS is configured.
        pytest.param(
            lambda: jwt.encode(_claims(), SECRET, algorithm="HS256"), id="hs256-no-secret"
        ),
        pytest.param(lambda: "not.a.jwt", id="garbage"),
    ],
)
async def test_bad_tokens_are_401(jwks: None, token: Any) -> None:
    assert await _status(token()) == 401


async def test_tampered_payload_is_401(jwks: None) -> None:
    header, _, sig = _es256().split(".")
    forged = base64url_encode(json.dumps(_claims(sub="someone-else")).encode()).decode()
    assert await _status(f"{header}.{forged}.{sig}") == 401


async def test_missing_sub_is_401_not_500(jwks: None) -> None:
    token = jwt.encode(
        {"aud": "authenticated", "exp": int(time.time()) + 60},
        EC_KEY,
        algorithm="ES256",
        headers={"kid": KID},
    )
    assert await _status(token) == 401


async def test_jwks_fetch_failure_is_503(jwks: None, monkeypatch: pytest.MonkeyPatch) -> None:
    def down(self: jwt.PyJWKClient) -> None:
        raise jwt.PyJWKClientConnectionError("connection refused")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", down)
    assert await _status(_es256()) == 503


async def test_hs256_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "supabase_url", None)
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    assert await _user(jwt.encode(_claims(), SECRET, algorithm="HS256")) == "user-123"
    wrong = "wrong-secret-also-at-least-32-bytes"
    assert await _status(jwt.encode(_claims(), wrong, algorithm="HS256")) == 401
    assert await _status(jwt.encode(_claims(aud="anon"), SECRET, algorithm="HS256")) == 401
    # ES256 token but no project URL configured: can't verify it.
    assert await _status(_es256()) == 401


async def test_both_configured_accepts_both(jwks: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    assert await _user(_es256()) == "user-123"
    assert await _user(jwt.encode(_claims(), SECRET, algorithm="HS256")) == "user-123"


async def test_neither_configured_is_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "supabase_url", None)
    monkeypatch.setattr(settings, "supabase_jwt_secret", None)
    assert await _status(_es256()) == 503


async def test_missing_bearer_is_401_even_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "supabase_url", None)
    monkeypatch.setattr(settings, "supabase_jwt_secret", None)
    with pytest.raises(HTTPException) as exc:
        await auth.get_current_user_id(None)
    assert exc.value.status_code == 401
