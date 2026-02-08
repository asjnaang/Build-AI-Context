"""
Secret redaction module for anything_to_text.

Automatically redacts tokens, API keys, passwords, and other secrets
from source code before bundling.
"""

from __future__ import annotations

import re
from typing import Pattern

REDACTION_MARK = "<REDACTED>"

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# JWT tokens (three base64 segments)
_RE_JWT = re.compile(
    r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"
)

# Authorization: Bearer <token>
_RE_BEARER = re.compile(
    r"(Authorization\s*:\s*Bearer\s+)([A-Za-z0-9\-_\.=]+)",
    flags=re.IGNORECASE,
)
_RE_BEARER_JSON = re.compile(
    r'("Authorization"\s*:\s*")Bearer\s+[^"]+(")',
    flags=re.IGNORECASE,
)

# API key patterns in headers/variables
_RE_API_KEY_HEADER = re.compile(
    r'(?i)((?:x-api-key|api-key|apikey|api_key)["\s:=]+)(["\']?[A-Za-z0-9_\-\.]{8,}["\']?)',
)

# JSON-style secret keys
_RE_JSON_SECRET = re.compile(
    r'(?i)("(?:api[_-]?key|token|secret|password|client[_-]?secret|access[_-]?token|'
    r'refresh[_-]?token|bearer|auth_token|private[_-]?key|credentials)"'
    r'\s*:\s*)"[^"]*"',
)

# YAML-style secrets
_RE_YAML_SECRET = re.compile(
    r'(?i)(api[_-]?key|token|secret|password|client[_-]?secret|access[_-]?token|'
    r'refresh[_-]?token|bearer|auth_token|private[_-]?key|credentials)'
    r'\s*:\s*(\S+)',
)

# URL query params with secrets
_RE_URL_SECRET = re.compile(
    r"(?i)\b((?:token|access_token|refresh_token|api_key|apikey|key|secret|"
    r"sig|signature|auth|bearer|password|passwd|pwd)=)([^&\s\"]+)",
)

# Private key blocks
_RE_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    flags=re.DOTALL,
)

# ENV-style secrets (UPPERCASE keys only to avoid false positives)
# Matches keys ending with secret-indicating words
_RE_ENV_SECRET = re.compile(
    r"(?m)^\s*(?:export\s+)?"
    r"(?P<key>[A-Z][A-Z0-9_]*"
    r"(?:TOKEN|API_KEY|SECRET|PASSWORD|PASS|ACCESS_KEY|PRIVATE_KEY|CLIENT_SECRET|"
    r"AUTH|BEARER|CREDENTIALS|KEY|CREDENTIALS|SIGNING|CLIENT_ID|APIPASSWORD)"
    r"[A-Z0-9_]*)"
    r"\s*=\s*(?P<val>.*)$",
)

# Base64-encoded secrets in assignments (e.g., secret_key = "dGhpcyBpcyBhIHNlY3JldA==")
_RE_BASE64_SECRET = re.compile(
    r'(?i)((?:secret|private|signing)[_-]?key(?:_[a-z]+)?)\s*=\s*[\'"]([A-Za-z0-9+/]{20,}={0,2})[\'"]',
)

# Generic hex token assignments (32+ hex chars)
_RE_HEX_TOKEN = re.compile(
    r'(?i)((?:secret|token|key|password|auth)[_-]?(?:key|value|hash)?)\s*=\s*[\'"]([0-9a-f]{32,})[\'"]',
)

# AWS-style keys
_RE_AWS_KEY = re.compile(
    r"(AKIA[0-9A-Z]{16})"
)

# GitHub tokens
_RE_GITHUB_TOKEN = re.compile(
    r"(gh[pousr]_[A-Za-z0-9_]{36,251})"
)

# Slack tokens
_RE_SLACK_TOKEN = re.compile(
    r"(xox[bpors]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*)",
)

# Google API key
_RE_GOOGLE_API_KEY = re.compile(
    r"(AIza[0-9A-Za-z\-_]{35})"
)

# Stripe keys
_RE_STRIPE_KEY = re.compile(
    r"(sk_live_[0-9a-zA-Z]{24,})"
)

# Twilio API keys
_RE_TWILIO_KEY = re.compile(
    r"(SK[0-9a-fA-F]{32})"
)


def redact_text(text: str) -> str:
    """
    Redact secrets, tokens, and keys from text while preserving structure.

    This function is safe to call on any source code and will not break
    the file structure - it only replaces secret values with <REDACTED>.
    """
    if not text or not isinstance(text, str):
        return text if text else ""

    # Private key blocks (preserve structure)
    text = _RE_PRIVATE_KEY_BLOCK.sub(
        "-----BEGIN PRIVATE KEY-----\n<REDACTED>\n-----END PRIVATE KEY-----",
        text,
    )

    # Authorization headers
    text = _RE_BEARER.sub(rf"\1{REDACTION_MARK}", text)
    text = _RE_BEARER_JSON.sub(rf'\1Bearer {REDACTION_MARK}\2', text)

    # API key headers
    text = _RE_API_KEY_HEADER.sub(rf"\1{REDACTION_MARK}", text)

    # JWTs
    text = _RE_JWT.sub(REDACTION_MARK, text)

    # Cloud provider tokens
    text = _RE_AWS_KEY.sub(REDACTION_MARK, text)
    text = _RE_GITHUB_TOKEN.sub(REDACTION_MARK, text)
    text = _RE_SLACK_TOKEN.sub(REDACTION_MARK, text)
    text = _RE_GOOGLE_API_KEY.sub(REDACTION_MARK, text)
    text = _RE_STRIPE_KEY.sub(REDACTION_MARK, text)
    text = _RE_TWILIO_KEY.sub(REDACTION_MARK, text)

    # JSON secrets
    text = _RE_JSON_SECRET.sub(rf'\1"{REDACTION_MARK}"', text)

    # YAML secrets (be careful not to break non-secret YAML)
    def _redact_yaml(m: re.Match) -> str:
        key = m.group(1)
        val = m.group(2).strip()
        if not val or val in ('""', "''", "null", "~"):
            return m.group(0)
        return f"{key}: {REDACTION_MARK}"
    text = _RE_YAML_SECRET.sub(_redact_yaml, text)

    # URL query secrets
    text = _RE_URL_SECRET.sub(rf"\1{REDACTION_MARK}", text)

    # Base64 secrets
    text = _RE_BASE64_SECRET.sub(rf'\1="{REDACTION_MARK}"', text)

    # Hex token assignments
    text = _RE_HEX_TOKEN.sub(rf"\1='{REDACTION_MARK}'", text)

    # ENV secrets (UPPERCASE only)
    def _redact_env_line(m: re.Match) -> str:
        key = m.group("key")
        val = (m.group("val") or "").rstrip()

        if val.strip() == "":
            return m.group(0)

        v = val.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            q = v[0]
            return f"{key}={q}{REDACTION_MARK}{q}"
        return f"{key}={REDACTION_MARK}"

    text = _RE_ENV_SECRET.sub(_redact_env_line, text)

    return text


def redact_lines(lines: list[str]) -> list[str]:
    """Redact secrets from a list of lines."""
    return [redact_text(line) for line in lines]
