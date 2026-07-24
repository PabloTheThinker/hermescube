"""Peer card — structured user model without LLM dialectic (original).

Nous/Honcho parallel: peer card + base context refreshed on cadence.
Cube version: assemble from warehouse types (trait/relationship/belief)
into memories/peer_card.json + prompt strip. No cloud, no dialectic LLM.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def card_path(hermes_home: str | Path | None = None) -> Path:
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    return hh / "memories" / "peer_card.json"


def _pick(entries: list[Any], etypes: set[str], *, limit: int = 8) -> list[str]:
    out: list[str] = []
    for e in entries:
        et = (getattr(e, "entry_type", "") or "").lower()
        if et not in etypes:
            continue
        if (getattr(e, "outcome", "") or "") == "superseded":
            continue
        d = (getattr(e, "description", "") or "").strip()
        if not d or d.startswith("["):
            continue
        try:
            from hermescube.journey import is_noise_text

            if is_noise_text(d):
                continue
        except Exception:
            pass
        out.append(d[:160])
        if len(out) >= limit:
            break
    return out


def build_card(entries: list[Any], *, peer_name: str = "user") -> dict[str, Any]:
    """Build structured card from cube entries."""
    # newest first for picks
    ents = sorted(
        entries,
        key=lambda e: getattr(e, "timestamp", "") or "",
        reverse=True,
    )
    traits = _pick(ents, {"trait"}, limit=6)
    relationships = _pick(ents, {"relationship"}, limit=6)
    beliefs = _pick(ents, {"belief"}, limit=8)
    focuses = []
    try:
        from hermescube.prospective import open_focuses

        focuses = [
            (e.description or "")[:120]
            for e in open_focuses(ents, limit=4)
            if e.description
        ]
    except Exception:
        pass
    # name hint from relationship-like "X = role"
    name = peer_name
    for r in relationships + beliefs:
        if "=" in r and len(r) < 80:
            left = r.split("=", 1)[0].strip()
            if (
                left
                and len(left.split()) <= 4
                and "." not in left
                and not left.lower().startswith("confirmed")
            ):
                name = left
                break
    return {
        "v": 1,
        "peer_name": name,
        "traits": traits,
        "relationships": relationships,
        "beliefs": beliefs[:6],
        "open_intents": focuses,
        "updated_ts": time.time(),
        "updated_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "hermescube_peer_card",
    }


def save_card(card: dict[str, Any], hermes_home: str | Path | None = None) -> Path:
    path = card_path(hermes_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_card(hermes_home: str | Path | None = None) -> dict[str, Any] | None:
    path = card_path(hermes_home)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def refresh_card(
    entries: list[Any],
    *,
    hermes_home: str | Path | None = None,
    peer_name: str = "user",
    min_interval_s: float = 0.0,
) -> dict[str, Any]:
    """Rebuild card unless within cadence interval."""
    prev = load_card(hermes_home)
    if prev and min_interval_s > 0:
        age = time.time() - float(prev.get("updated_ts") or 0)
        if age < min_interval_s:
            return {"skipped": True, "age_s": age, "card": prev}
    card = build_card(entries, peer_name=peer_name)
    path = save_card(card, hermes_home)
    return {"skipped": False, "path": str(path), "card": card}


def prompt_strip(card: dict[str, Any] | None, *, max_lines: int = 6) -> str:
    if not card:
        return ""
    lines = [f"### Peer card ({card.get('peer_name') or 'user'})"]
    for key, label in (
        ("traits", "Traits"),
        ("relationships", "Relations"),
        ("beliefs", "Beliefs"),
        ("open_intents", "Open intents"),
    ):
        items = card.get(key) or []
        if not items:
            continue
        lines.append(f"- {label}: " + " · ".join(str(x)[:60] for x in items[:3]))
        if len(lines) >= max_lines + 1:
            break
    return "\n".join(lines) if len(lines) > 1 else ""
