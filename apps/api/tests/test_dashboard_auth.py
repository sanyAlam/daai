from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest

from app.dashboard_auth import DashboardAuthError, verify_supabase_access_token


def _access_token(claims: dict[str, object], secret: str = "test-signing-secret") -> str:
    payload = dict(claims)
    payload.setdefault("aud", "authenticated")
    payload.setdefault(
        "exp",
        int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    )
    return jwt.encode(payload, secret, algorithm="HS256")


def test_hmac_token_without_configured_jwt_secret_has_clear_error() -> None:
    token = _access_token({"sub": str(uuid4())})

    with pytest.raises(DashboardAuthError) as raised:
        verify_supabase_access_token(
            authorization_header=f"Bearer {token}",
            jwt_secret=None,
            supabase_url="https://project-ref.supabase.co",
        )

    message = str(raised.value)
    assert "missing DAAI_SUPABASE_JWT_SECRET" in message


def test_supabase_user_endpoint_fallback_verifies_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    token = _access_token({"sub": str(user_id)})

    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_: object) -> bool:
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "id": str(user_id),
                    "email": "owner@example.com",
                }
            ).encode("utf-8")

    def _fake_urlopen(request: object, timeout: int = 5) -> _Response:
        assert timeout == 5
        request_url = getattr(request, "full_url")
        assert request_url == "https://project-ref.supabase.co/auth/v1/user"
        headers = getattr(request, "headers")
        assert headers.get("Apikey") == "sb_secret_example_key"
        assert headers.get("Authorization") == f"Bearer {token}"
        return _Response()

    monkeypatch.setattr("app.dashboard_auth.urlopen", _fake_urlopen)

    principal = verify_supabase_access_token(
        authorization_header=f"Bearer {token}",
        jwt_secret="sb_secret_example_key",
        supabase_url="https://project-ref.supabase.co",
    )

    assert principal.user_id == UUID(str(user_id))
    assert principal.email == "owner@example.com"
