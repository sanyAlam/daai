from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

import jwt
from jwt import InvalidTokenError, PyJWKClient


class DashboardAuthError(PermissionError):
    """Raised when dashboard bearer auth is missing or invalid."""


@dataclass(frozen=True)
class DashboardPrincipal:
    user_id: UUID
    email: str | None


@dataclass(frozen=True)
class DashboardTokenMetadata:
    algorithm: str | None
    issuer: str | None
    subject: str | None


_JWKS_CLIENTS: dict[str, PyJWKClient] = {}
_SUPABASE_ACCESS_TOKEN_AUDIENCE = "authenticated"


def extract_bearer_token(authorization_header: str) -> str:
    if not authorization_header:
        raise DashboardAuthError("missing authorization header")

    prefix = "Bearer "
    if not authorization_header.startswith(prefix):
        raise DashboardAuthError("invalid authorization header format")

    token = authorization_header[len(prefix) :].strip()
    if not token:
        raise DashboardAuthError("missing bearer token")
    return token


def inspect_unverified_token(authorization_header: str) -> DashboardTokenMetadata:
    token = extract_bearer_token(authorization_header)
    return _inspect_unverified_token(token)


def verify_supabase_access_token(
    authorization_header: str,
    jwt_secret: str | None,
    supabase_url: str | None = None,
) -> DashboardPrincipal:
    token = extract_bearer_token(authorization_header)
    metadata = _inspect_unverified_token(token)

    expected_issuer = _build_expected_issuer(supabase_url)
    if expected_issuer and metadata.issuer and metadata.issuer != expected_issuer:
        raise DashboardAuthError(
            "dashboard token issuer mismatch "
            f"(expected {expected_issuer}, got {metadata.issuer})"
        )

    verification_errors: list[str] = []
    verified_claims: dict[str, Any] | None = None
    supabase_api_key = _resolve_supabase_api_key(jwt_secret)

    if _is_hmac_algorithm(metadata.algorithm):
        if not jwt_secret:
            verification_errors.append(
                "missing DAAI_SUPABASE_JWT_SECRET for HMAC-signed dashboard token"
            )
        else:
            try:
                verified_claims = jwt.decode(
                    token,
                    jwt_secret,
                    algorithms=[metadata.algorithm or "HS256"],
                    options={"require": ["exp", "sub"]},
                    issuer=expected_issuer,
                    audience=_SUPABASE_ACCESS_TOKEN_AUDIENCE,
                )
            except InvalidTokenError as exc:
                verification_errors.append(f"HMAC verification failed: {exc}")

    if verified_claims is None:
        if not metadata.issuer:
            verification_errors.append("token issuer claim (iss) is missing")
        else:
            jwks_url = _build_jwks_url(metadata.issuer)
            if jwks_url is None:
                verification_errors.append(
                    f"token issuer is not a valid URL: {metadata.issuer}"
                )
            else:
                try:
                    jwks_client = _get_jwks_client(jwks_url)
                    signing_key = jwks_client.get_signing_key_from_jwt(token)
                    verified_claims = jwt.decode(
                        token,
                        signing_key.key,
                        algorithms=[metadata.algorithm] if metadata.algorithm else None,
                        options={"require": ["exp", "sub"]},
                        issuer=expected_issuer or metadata.issuer,
                        audience=_SUPABASE_ACCESS_TOKEN_AUDIENCE,
                    )
                except Exception as exc:  # noqa: BLE001 - surface precise auth diagnostics
                    verification_errors.append(f"JWKS verification failed: {exc}")

    if verified_claims is None and supabase_url and supabase_api_key:
        try:
            verified_claims = _verify_with_supabase_auth_server(
                token=token,
                supabase_url=supabase_url,
                api_key=supabase_api_key,
            )
        except DashboardAuthError as exc:
            verification_errors.append(str(exc))

    if verified_claims is None:
        if not verification_errors:
            verification_errors.append("unknown verification failure")
        raise DashboardAuthError(
            "invalid dashboard access token: " + "; ".join(verification_errors)
        )

    return DashboardPrincipal(
        user_id=_parse_sub(verified_claims),
        email=_parse_email(verified_claims),
    )


def _inspect_unverified_token(token: str) -> DashboardTokenMetadata:
    algorithm: str | None = None
    issuer: str | None = None
    subject: str | None = None

    try:
        header = jwt.get_unverified_header(token)
        header_algorithm = header.get("alg")
        if isinstance(header_algorithm, str) and header_algorithm:
            algorithm = header_algorithm
    except Exception:
        algorithm = None

    try:
        claims = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=["HS256", "HS384", "HS512", "RS256", "ES256"],
        )
        token_issuer = claims.get("iss")
        token_subject = claims.get("sub")
        if isinstance(token_issuer, str) and token_issuer:
            issuer = token_issuer
        if isinstance(token_subject, str) and token_subject:
            subject = token_subject
    except Exception:
        issuer = None
        subject = None

    return DashboardTokenMetadata(
        algorithm=algorithm,
        issuer=issuer,
        subject=subject,
    )


def _is_hmac_algorithm(algorithm: str | None) -> bool:
    return algorithm in {"HS256", "HS384", "HS512"}


def _resolve_supabase_api_key(jwt_secret: str | None) -> str | None:
    if not jwt_secret:
        return None
    if jwt_secret.startswith("sb_publishable_") or jwt_secret.startswith("sb_secret_"):
        return jwt_secret
    return None


def _build_expected_issuer(supabase_url: str | None) -> str | None:
    if not supabase_url:
        return None
    normalized = supabase_url.rstrip("/")
    if not normalized:
        return None
    return f"{normalized}/auth/v1"


def _build_jwks_url(issuer: str) -> str | None:
    parsed = urlparse(issuer)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return issuer.rstrip("/") + "/.well-known/jwks.json"


def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    client = _JWKS_CLIENTS.get(jwks_url)
    if client is None:
        client = PyJWKClient(jwks_url)
        _JWKS_CLIENTS[jwks_url] = client
    return client


def _parse_sub(claims: dict[str, Any]) -> UUID:
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise DashboardAuthError("dashboard token subject is missing")
    try:
        return UUID(sub)
    except ValueError as exc:
        raise DashboardAuthError("dashboard token subject is invalid") from exc


def _parse_email(claims: dict[str, Any]) -> str | None:
    email = claims.get("email")
    if isinstance(email, str) and email:
        return email
    return None


def _verify_with_supabase_auth_server(
    token: str,
    supabase_url: str,
    api_key: str,
) -> dict[str, Any]:
    normalized_url = supabase_url.rstrip("/")
    if not normalized_url:
        raise DashboardAuthError("Supabase /auth/v1/user verification is not configured")

    request = Request(
        f"{normalized_url}/auth/v1/user",
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=5) as response:
            payload = _parse_json_payload(response.read())
    except HTTPError as exc:
        body = _safe_decode(exc.read())
        detail = _extract_supabase_error_detail(body) or exc.reason
        raise DashboardAuthError(
            f"Supabase /auth/v1/user rejected token ({exc.code}): {detail}"
        ) from exc
    except URLError as exc:
        raise DashboardAuthError(
            f"Supabase /auth/v1/user verification failed: {exc.reason}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - preserve detailed diagnostics for logs
        raise DashboardAuthError(
            f"Supabase /auth/v1/user verification failed: {exc}"
        ) from exc

    user_id = payload.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise DashboardAuthError(
            "Supabase /auth/v1/user payload is missing a valid id field"
        )

    claims: dict[str, Any] = {"sub": user_id}
    user_email = payload.get("email")
    if isinstance(user_email, str) and user_email:
        claims["email"] = user_email
    return claims


def _parse_json_payload(data: bytes) -> dict[str, Any]:
    try:
        decoded = json.loads(data.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - preserve exact failure reason
        raise DashboardAuthError(f"invalid JSON from Supabase auth server: {exc}") from exc
    if not isinstance(decoded, dict):
        raise DashboardAuthError("invalid JSON object from Supabase auth server")
    return decoded


def _extract_supabase_error_detail(body: str) -> str | None:
    if not body:
        return None
    try:
        parsed = json.loads(body)
    except Exception:
        return body
    if not isinstance(parsed, dict):
        return body
    for field in ("error_description", "msg", "message", "error"):
        value = parsed.get(field)
        if isinstance(value, str) and value:
            return value
    return body


def _safe_decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except Exception:
        return ""
