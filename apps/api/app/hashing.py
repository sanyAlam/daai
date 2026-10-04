import hashlib


def hash_api_key(api_key: str, pepper: str) -> str:
    payload = f"{pepper}:{api_key}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hash_workspace_key(workspace_key: str, pepper: str) -> str:
    payload = f"{pepper}:{workspace_key}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hash_approval_token(token: str, pepper: str) -> str:
    payload = f"{pepper}:{token}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hash_rate_limit_key(value: str, pepper: str) -> str:
    payload = f"{pepper}:{value}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
