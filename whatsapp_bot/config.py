"""
Configuration — env vars + defaults.

Loads .env from whatsapp_bot/.env or project root .env if present.
Falls back to MOCK_MODE=true so a fresh clone is runnable without any
Twilio or Gemini credentials.
"""

from __future__ import annotations
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    # Try whatsapp_bot/.env first, then project-root .env
    _here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(_here, ".env"),
        os.path.join(_here, "..", ".env"),
    ):
        if os.path.exists(candidate):
            load_dotenv(candidate)
            break
except ImportError:
    # python-dotenv not installed — env must be set externally
    pass


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Mock mode short-circuits Gemini + Twilio signature validation so the
    # bot is runnable end-to-end without external accounts. Default True
    # so fresh clones work; flip to false for production.
    mock_mode: bool = _bool(os.getenv("MOCK_MODE"), default=True)

    # Twilio
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_whatsapp_from: str = os.getenv(
        "TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"  # Twilio sandbox default
    )
    # Disable signature validation entirely (use only for local curl testing).
    twilio_validate_signature: bool = _bool(
        os.getenv("TWILIO_VALIDATE_SIGNATURE"), default=False
    )

    # Gemini
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # Server
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")


settings = Settings()
