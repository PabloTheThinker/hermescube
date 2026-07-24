"""Trajectory observe — successful tool chains → procedure drafts (original).

Dawson-lite / skills-from-experience without media:
  Watch *what the agent actually did* (tool trajectories), not YouTube.
  Operator-gated drafts under memories/procedures/ — never silent skill_manage.

Wires:
  on_session_end / on_pre_compress / on_delegation
  hermescube_manage action=observe

Gates (anti-sprawl):
  - ≥ min_tools distinct tool steps
  - skip pure memory/search thrash
  - scrub secrets / absolute home paths from draft text
  - dedupe by trajectory fingerprint
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|password|secret|authorization|bearer)\s*[:=]\s*\S+"
)
_PATH_RE = re.compile(r"(/home/[a-z0-9._-]+|/Users/[a-z0-9._-]+)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Tools that alone don't make a "how we worked" procedure
_SKIP_ONLY = frozenset(
    {
        "hermescube_search",
        "hermescube_probe",
        "hermescube_manage",
        "hermescube_feedback",
        "memory",
        "session_search",
        "skill_view",
        "skills_list",
        "todo",
        "clarify",
    }
)


def _slug(text: str, max_len: int = 48) -> str:
    s = _SLUG_RE.sub("-", (text or "").lower()).strip("-")
    return (s[:max_len] or "trajectory").strip("-")


def scrub(text: str) -> str:
    t = _SECRET_RE.sub(r"\1=***", text or "")
    t = _PATH_RE.sub("$HOME", t)
    return t[:4000]


def _tool_name(tc: Any) -> str:
    if not isinstance(tc, dict):
        return ""
    if "function" in tc and isinstance(tc["function"], dict):
        return str(tc["function"].get("name") or "")
    return str(tc.get("name") or tc.get("tool_name") or "")


def _tool_args(tc: Any) -> str:
    if not isinstance(tc, dict):
        return ""
    fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
    args = fn.get("arguments") if fn else tc.get("arguments") or tc.get("input")
    if args is None:
        return ""
    if isinstance(args, dict):
        try:
            return json.dumps(args, ensure_ascii=False)[:300]
        except Exception:
            return str(args)[:300]
    return str(args)[:300]


def extract_trajectories(
    messages: list[dict[str, Any]] | None,
    *,
    min_tools: int = 3,
    max_traj: int = 5,
) -> list[dict[str, Any]]:
    """Pull multi-tool episodes from a message list."""
    if not messages:
        return []
    trajs: list[dict[str, Any]] = []
    pending_tools: list[dict[str, str]] = []
    last_user = ""

    def flush() -> None:
        nonlocal pending_tools
        if len(pending_tools) < min_tools:
            pending_tools = []
            return
        names = [t["name"] for t in pending_tools if t.get("name")]
        nontrivial = [n for n in names if n not in _SKIP_ONLY]
        if len(nontrivial) < 2 and len(names) < min_tools + 1:
            pending_tools = []
            return
        # skip all-skip tool chains
        if not nontrivial:
            pending_tools = []
            return
        fp = hashlib.sha256("|".join(names).encode()).hexdigest()[:12]
        goal = (last_user or "session work").strip()[:200]
        trajs.append(
            {
                "goal": scrub(goal),
                "tools": list(pending_tools),
                "tool_names": names,
                "fingerprint": fp,
                "n_tools": len(pending_tools),
            }
        )
        pending_tools = []

    for m in messages:
        if not isinstance(m, dict):
            continue
        role = (m.get("role") or "").lower()
        if role == "user":
            flush()
            content = m.get("content") or ""
            if isinstance(content, list):
                content = " ".join(
                    str(p.get("text") or "") if isinstance(p, dict) else str(p)
                    for p in content
                )
            last_user = str(content)[:300]
        elif role == "assistant":
            tcs = m.get("tool_calls") or m.get("toolCalls") or []
            if isinstance(tcs, list):
                for tc in tcs:
                    name = _tool_name(tc)
                    if not name:
                        continue
                    pending_tools.append(
                        {"name": name, "args": scrub(_tool_args(tc))}
                    )
        elif role == "tool":
            # optional: note tool result success keywords
            pass

    flush()
    # prefer longer chains
    trajs.sort(key=lambda t: t.get("n_tools", 0), reverse=True)
    return trajs[:max_traj]


def _already_forged(cube: Any, fingerprint: str) -> bool:
    try:
        for e in cube.read_l1() or []:
            d = e.data if isinstance(getattr(e, "data", None), dict) else {}
            if d.get("trajectory_fp") == fingerprint:
                return True
            if d.get("forged_from") == f"traj:{fingerprint}":
                return True
    except Exception:
        pass
    return False


def forge_trajectory(
    cube: Any,
    traj: dict[str, Any],
    *,
    hermes_home: str | Path | None = None,
    write_draft: bool = True,
) -> dict[str, Any]:
    """Write one evolution entry + optional draft SKILL from a trajectory."""
    out: dict[str, Any] = {"forged": False}
    if cube is None or not traj:
        return out
    fp = str(traj.get("fingerprint") or "")
    if not fp or _already_forged(cube, fp):
        out["skipped"] = "duplicate_or_empty"
        return out

    goal = scrub(str(traj.get("goal") or "workflow"))
    names = traj.get("tool_names") or [t.get("name") for t in traj.get("tools") or []]
    names = [str(n) for n in names if n]
    steps = traj.get("tools") or []

    desc = f"Trajectory: {goal[:120]} via {' → '.join(names[:8])}"
    try:
        added = cube.append(
            entry_type="evolution",
            description=f"[TRAJECTORY] {desc[:220]}",
            data={
                "procedure": True,
                "trajectory": True,
                "trajectory_fp": fp,
                "forged_from": f"traj:{fp}",
                "source": "trajectory_observe",
                "tool_names": names[:20],
                "trust": 0.78,
                "durable": True,
            },
            outcome="success",
        )
        out["entry_id"] = getattr(added, "id", None)
        out["forged"] = True
    except Exception as e:
        out["error"] = str(e)
        return out

    if write_draft:
        hh = Path(
            hermes_home
            or os.environ.get("HERMES_HOME")
            or (Path.home() / ".hermes")
        )
        ddir = hh / "memories" / "procedures"
        ddir.mkdir(parents=True, exist_ok=True)
        slug = _slug(goal)
        path = ddir / f"traj-{slug}-{fp[:8]}.md"
        step_lines = []
        for i, s in enumerate(steps[:15], 1):
            step_lines.append(
                f"{i}. **{s.get('name')}** — `{(s.get('args') or '')[:160]}`"
            )
        if not step_lines:
            step_lines = [f"{i}. **{n}**" for i, n in enumerate(names[:15], 1)]
        body = f"""---
name: traj-{slug[:40]}
description: "Draft from observed tool trajectory (not auto-installed)."
version: 0.1.0-draft
origin: hermescube-trajectory-observe
trajectory_fp: {fp}
---

# {goal[:80]}

> **Draft** — learned by watching a successful multi-tool run. Review before `skill_manage`.

## When to use
- Similar goal: {goal}

## Observed procedure
{chr(10).join(step_lines)}

## Tool chain
`{' → '.join(names[:12])}`

## Verification
- [ ] Still valid on this host
- [ ] No secrets in args
- [ ] Ready to promote to a real skill (optional)

## Notes
Forged {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} by HermesCube trajectory observe.
Cube entry: `{out.get("entry_id")}`
"""
        path.write_text(body, encoding="utf-8")
        out["draft"] = str(path)

    try:
        from hermescube.journey import log_event

        log_event(
            "trajectory_observe",
            f"Forged trajectory draft: {goal[:100]}",
            hermes_home=hermes_home,
            entry_id=str(out.get("entry_id") or ""),
            meta={"fp": fp, "n_tools": len(names)},
        )
    except Exception:
        pass
    return out


def observe_messages(
    cube: Any,
    messages: list[dict[str, Any]] | None,
    *,
    hermes_home: str | Path | None = None,
    min_tools: int = 3,
    max_forge: int = 3,
    write_drafts: bool = True,
) -> dict[str, Any]:
    """Extract trajectories and forge up to max_forge new drafts."""
    stats: dict[str, Any] = {
        "trajectories": 0,
        "forged": 0,
        "drafts": [],
        "skipped": 0,
    }
    if cube is None:
        return stats
    trajs = extract_trajectories(messages, min_tools=min_tools)
    stats["trajectories"] = len(trajs)
    for t in trajs[:max_forge]:
        r = forge_trajectory(
            cube, t, hermes_home=hermes_home, write_draft=write_drafts
        )
        if r.get("forged"):
            stats["forged"] += 1
            if r.get("draft"):
                stats["drafts"].append(r["draft"])
        else:
            stats["skipped"] += 1
    return stats


def observe_delegation(
    cube: Any,
    task: str,
    result: str,
    *,
    hermes_home: str | Path | None = None,
    child_session_id: str = "",
) -> dict[str, Any]:
    """Parent-side: store a resolve-shaped note from subagent completion."""
    out: dict[str, Any] = {"stored": False}
    if cube is None or not (task or "").strip():
        return out
    try:
        from hermescube.journey import is_noise_text

        if is_noise_text(task):
            return out
    except Exception:
        pass
    summary = scrub(f"Delegated: {task.strip()[:160]} → {(result or '')[:120]}")
    try:
        e = cube.append(
            entry_type="resolve",
            description=summary[:280],
            data={
                "source": "trajectory_delegation",
                "child_session_id": child_session_id or "",
                "trust": 0.7,
                "durable": True,
            },
            outcome="success",
        )
        out["stored"] = True
        out["id"] = getattr(e, "id", None)
        # try close prospective focus
        try:
            from hermescube.prospective import try_close_on_resolve

            out["prospective"] = try_close_on_resolve(cube, e)
        except Exception:
            pass
    except Exception as ex:
        out["error"] = str(ex)
    return out
