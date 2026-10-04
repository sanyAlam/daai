from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DAAI_", extra="ignore")

    database_url: Optional[str] = Field(default=None)
    supabase_url: Optional[str] = Field(default=None)
    supabase_jwt_secret: Optional[str] = Field(default=None)
    api_key_pepper: str = Field(default="dev-only-change-me")
    workspace_key_pepper: str = Field(default="dev-only-change-me")
    approval_token_pepper: str = Field(default="dev-only-change-me")
    approval_token_ttl_seconds: int = Field(default=86400, ge=1)
    public_base_url: str = Field(default="http://127.0.0.1:8000")
    dashboard_base_url: str = Field(default="http://127.0.0.1:3000")
    approval_email_provider: str = Field(default="log")
    approval_email_from: str = Field(default="no-reply@daai.local")
    resend_api_key: Optional[str] = Field(default=None)
    open_ai_api_key: Optional[str] = Field(default=None)
    policy_model: str = Field(default="gpt-5.4-mini")
    cors_origins: str = Field(
        default="http://localhost:3000"
    )
    dev_approval_link_logging_enabled: bool = Field(default=False)
    dev_auto_link_seeded_workspace: bool = Field(default=False)
    dev_seeded_workspace_id: str = Field(
        default="11111111-1111-1111-1111-111111111111"
    )
    admin_emails: str = Field(default="")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
