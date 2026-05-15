"""
Twilio helpers — TwiML response building + signature validation.

Imported lazily inside functions so the package doesn't hard-require
the twilio SDK in mock mode.
"""

from __future__ import annotations
from typing import Mapping
from xml.sax.saxutils import escape


def make_twiml_response(message: str) -> str:
    """
    Build a TwiML <Response><Message> reply.
    Twilio expects this XML body as the webhook response.
    """
    safe = escape(message or "")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{safe}</Message></Response>"
    )


def validate_signature(
    auth_token: str,
    signature: str,
    url: str,
    form: Mapping[str, str],
) -> bool:
    """
    Validate X-Twilio-Signature header against the request URL + form params.
    Returns True if valid OR if validation can't be performed (no SDK installed
    in mock-mode contexts). Caller decides whether to enforce.
    """
    if not auth_token or not signature:
        return False
    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        return False
    validator = RequestValidator(auth_token)
    return validator.validate(url, dict(form), signature)
