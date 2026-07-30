"""Secret redaction for flight records (defaults ON)."""
from __future__ import annotations

import re
from typing import Any

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "aws_secret_key",
        re.compile(
            r"(?i)(aws_secret_access_key|secret_access_key)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{30,})"
        ),
    ),
    ("github_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("github_fine_grained", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("openai_proj_key", re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b")),
    ("xai_key", re.compile(r"\bxai-[A-Za-z0-9_]{20,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b")),
    (
        "bearer",
        re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)([A-Za-z0-9\-._~+/]+=*)"),
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    (
        "private_key_block",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
    ),
    (
        "pem_cert_adjacent_key",
        re.compile(
            r"(?i)(api[_-]?key|access[_-]?token|secret|password|passwd|token)\s*[:=]\s*['\"]([^'\"\s]{12,})['\"]"
        ),
    ),
    (
        "connection_string",
        re.compile(
            r"(?i)\b((?:postgres|mysql|mongodb|redis|amqp)://)([^/\s:@]+):([^@\s]+)@"
        ),
    ),
    (
        "hermes_a2a_tokenish",
        re.compile(
            r"(?i)(auth_token|bearer_token|a2a_token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{16,})"
        ),
    ),
]


def redact_text(text: str | None) -> tuple[str | None, int]:
    if text is None:
        return None, 0
    if not isinstance(text, str):
        text = str(text)
    count = 0
    out = text
    for name, pat in _PATTERNS:

        def _sub(m: re.Match[str], _name: str = name) -> str:
            nonlocal count
            count += 1
            if m.lastindex and m.lastindex >= 2 and _name in {
                "bearer",
                "pem_cert_adjacent_key",
                "aws_secret_key",
                "connection_string",
                "hermes_a2a_tokenish",
            }:
                if _name == "connection_string":
                    return f"{m.group(1)}{m.group(2)}:[REDACTED]@"
                return f"{m.group(1)}[REDACTED:{_name}]"
            return f"[REDACTED:{_name}]"

        out, n = pat.subn(_sub, out)
        if n and count == 0:
            count += n
    return out, count


def redact_obj(value: Any) -> tuple[Any, int]:
    total = 0
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        out = []
        for item in value:
            red, n = redact_obj(item)
            total += n
            out.append(red)
        return out, total
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            kl = str(k).lower()
            if any(
                s in kl
                for s in (
                    "password",
                    "secret",
                    "token",
                    "api_key",
                    "apikey",
                    "auth",
                    "credential",
                    "private_key",
                )
            ):
                if v is None or v == "":
                    out[k] = v
                else:
                    out[k] = "[REDACTED:field]"
                    total += 1
                continue
            red, n = redact_obj(v)
            total += n
            out[k] = red
        return out, total
    return value, 0
