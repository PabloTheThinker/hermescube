"""Session digest — 5-line narrative without LLM (original).

Nous parallel: session summary in base context / FTS digests.
Cube: template from messages + open intents + tool chain hints.
"""

from __future__ import annotations

import re
from typing import Any

_TOOL_RE = re.compile(r"[a-z_][a-z0-9_]{2,}", re.I)


def _content(m: dict[str, Any]) -> str:
    c = m.get("content") or ""
    if isinstance(c, list):
        parts = []
        for p in c:
            if isinstance(p, dict):
                parts.append(str(p.get("text") or ""))
            else:
                parts.append(str(p))
        return " ".join(parts)
    return str(c)


def _tool_names(messages: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for m in messages or []:
        if (m.get("role") or "") != "assistant":
            continue
        for tc in m.get("tool_calls") or m.get("toolCalls") or []:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            n = str(fn.get("name") or tc.get("name") or "")
            if n:
                names.append(n)
    # unique preserve order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def digest_messages(
    messages: list[dict[str, Any]] | None,
    *,
    open_intents: list[str] | None = None,
    max_user: int = 2,
) -> str:
    """Return a compact multi-line session digest."""
    msgs = messages or []
    users = []
    for m in msgs:
        if (m.get("role") or "").lower() != "user":
            continue
        t = _content(m).strip().replace("\n", " ")
        if t and len(t) > 8:
            users.append(t[:100])
    tools = _tool_names(msgs)
    lines = ["Session digest:"]
    if users:
        lines.append("- User: " + " | ".join(users[-max_user:]))
    else:
        lines.append("- User: (no material user turns)")
    if tools:
        lines.append("- Tools: " + " → ".join(tools[:10]))
    else:
        lines.append("- Tools: (none)")
    if open_intents:
        lines.append("- Still open: " + " · ".join(open_intents[:3]))
    n_asst = sum(1 for m in msgs if (m.get("role") or "") == "assistant")
    lines.append(f"- Turns: user={len(users)} assistant≈{n_asst} tools={len(tools)}")
    return "\n".join(lines)


def digest_entry_description(digest_text: str) -> str:
    # single-line warehouse form
    body = " ".join(
        ln[2:].strip() if ln.startswith("- ") else ln
        for ln in digest_text.splitlines()
        if ln and not ln.startswith("Session digest")
    )
    return f"[SESSION] {body[:240]}"
