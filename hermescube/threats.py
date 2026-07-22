"""Injection and threat scanning for memory entries.

Scans text for prompt injection, system prompt manipulation,
and other adversarial patterns before persisting to cube.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class ThreatMatch(NamedTuple):
    pattern_name: str
    matched_text: str
    severity: str  # "block" or "warn"


# Patterns that indicate prompt injection or system manipulation
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "system_override",
        re.compile(
            r"(?:ignore|disregard|forget|override)\s+"
            r"(?:all\s+)?(?:previous|prior|above|system|your)\s+"
            r"(?:instructions?|prompts?|rules?|guidelines?|constraints?)",
            re.IGNORECASE,
        ),
        "block",
    ),
    (
        "role_hijack",
        re.compile(
            r"(?:you\s+are\s+now|act\s+as\s+if|pretend\s+you\s+are|"
            r"from\s+now\s+on\s+you\s+are|new\s+instructions?:)",
            re.IGNORECASE,
        ),
        "block",
    ),
    (
        "system_prompt_leak",
        re.compile(
            r"(?:print|show|reveal|output|repeat|echo)\s+"
            r"(?:your\s+)?(?:system\s+prompt|instructions?|initial\s+prompt|"
            r"hidden\s+instructions?|configuration)",
            re.IGNORECASE,
        ),
        "warn",
    ),
    (
        "delimiter_escape",
        re.compile(
            r"(?:<\|im_start\|>|<\|im_end\|>|<\|system\|>|<\|user\|>|<\|assistant\|>)",
            re.IGNORECASE,
        ),
        "block",
    ),
    (
        "xml_tag_injection",
        re.compile(
            r"</?(?:system|assistant|user|memory-context|function_call)[\s>]",
            re.IGNORECASE,
        ),
        "warn",
    ),
    (
        "instruction_override",
        re.compile(
            r"(?:new\s+task|new\s+objective|override\s+task|"
            r"disregard\s+previous\s+task|cancel\s+previous)",
            re.IGNORECASE,
        ),
        "block",
    ),
]


def scan_text(text: str) -> list[ThreatMatch]:
    """Scan text for injection/threat patterns.

    Returns list of ThreatMatch objects. Empty list = clean.
    """
    matches: list[ThreatMatch] = []
    for name, pattern, severity in _INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            matches.append(ThreatMatch(name, m.group(), severity))
    return matches


def has_blockable_threat(text: str) -> bool:
    """Return True if text contains a blockable threat pattern."""
    return any(m.severity == "block" for m in scan_text(text))


def sanitize_for_storage(text: str, char_limit: int = 0) -> str:
    """Sanitize text for storage: strip null bytes, enforce char limit.

    Does NOT scan for threats — call scan_text() separately.
    """
    cleaned = text.replace("\x00", "")
    if char_limit > 0:
        cleaned = cleaned[:char_limit]
    return cleaned.strip()
