"""Colony communication inside HermesCube — original stigmergy layer.

Not a port of Hermes holographic. Inspired by comparative ethology:

| Species | Nature | Cube mapping |
|---------|--------|----------------|
| **Ants** | Pheromone trails (stigmergy) | Edge weights between entity nodes; deposit on use, evaporate over time |
| **Bees** | Waggle dance (what + where) | Compact dance on entries: resource kind + location tokens |
| **Elephants** | Long social/spatial maps | Durable landmark/relationship nodes resist evaporation |
| **Dolphins** | Social calls / shared attention | Co-activation when dances share receivers |
| **Whales** | Culture / song routes | Markdown colony board = shared "song sheet" humans can read |

Memories don't only sit in a list — they **leave trails** others can follow.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from hermescube import mirror as mirror_mod

# Evaporation half-life (hours) — ant pheromone fade
_TRAIL_HALF_LIFE_H = 72.0
_DEPOSIT = 0.35
_MAX_EDGE = 5.0


def _now() -> float:
    return time.time()


def resource_kind(entry_type: str, description: str) -> str:
    """Bee: what kind of 'pollen' is this memory?"""
    et = (entry_type or "").lower()
    d = (description or "").lower()
    if et in ("relationship",) or " = " in (description or ""):
        return "social"
    if et in ("trait",) or "prefer" in d:
        return "preference"
    if et in ("resolve",) or any(w in d for w in ("fixed", "ship", "done")):
        return "skill"  # cultural know-how
    if et in ("landmark", "focus") or any(w in d for w in ("path", "mission", "$")):
        return "route"
    if et in ("belief", "evolution"):
        return "insight"
    return "general"


def dance_payload(entry: Any) -> dict[str, Any]:
    """Bee waggle: encode what + where from an entry."""
    desc = getattr(entry, "description", "") or ""
    et = getattr(entry, "entry_type", "") or ""
    data = getattr(entry, "data", None) or {}
    ents = []
    if isinstance(data, dict):
        ents = list(data.get("entities") or [])
    if not ents:
        ents = mirror_mod.extract_entities(desc)
    return {
        "kind": resource_kind(et, desc),
        "where": ents[:6],
        "id": str(getattr(entry, "id", "")),
        "type": et,
    }


class ColonyGraph:
    """Ant-style pheromone graph over entity nodes + optional markdown board."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.edges: dict[str, dict[str, float]] = defaultdict(dict)  # a -> b -> weight
        self.updated: dict[str, float] = {}  # edge key -> unix ts
        self.dances: dict[str, dict[str, Any]] = {}  # entry_id -> dance
        if self.path and self.path.is_file():
            self.load()

    def _ekey(self, a: str, b: str) -> str:
        x, y = sorted((a.lower(), b.lower()))
        return f"{x}||{y}"

    def _evaporate(self, w: float, age_h: float) -> float:
        if age_h <= 0:
            return w
        return w * math.exp(-age_h / _TRAIL_HALF_LIFE_H)

    def deposit(self, entities: list[str], *, amount: float = _DEPOSIT) -> None:
        """Ant trail: strengthen edges among co-occurring entities."""
        ents = [e.strip().lower() for e in entities if e and e.strip()]
        ents = list(dict.fromkeys(ents))  # unique order-preserve
        if len(ents) < 2:
            return
        now = _now()
        for i, a in enumerate(ents):
            for b in ents[i + 1 :]:
                k = self._ekey(a, b)
                age_h = (now - self.updated.get(k, now)) / 3600.0
                cur = self.edges[a].get(b, self.edges[b].get(a, 0.0))
                cur = self._evaporate(cur, age_h)
                cur = min(_MAX_EDGE, cur + amount)
                self.edges[a][b] = cur
                self.edges[b][a] = cur
                self.updated[k] = now

    def trail_boost(self, entities_a: list[str], entities_b: list[str]) -> float:
        """How strongly two memory sites are linked by pheromone."""
        if not entities_a or not entities_b:
            return 1.0
        now = _now()
        best = 0.0
        for a in entities_a:
            al = a.lower()
            for b in entities_b:
                bl = b.lower()
                if al == bl:
                    best = max(best, 1.0)
                    continue
                k = self._ekey(al, bl)
                w = self.edges.get(al, {}).get(bl, 0.0)
                age_h = (now - self.updated.get(k, now)) / 3600.0
                w = self._evaporate(w, age_h)
                best = max(best, w)
        # map weight → multiplier [1.0, 1.45]
        return 1.0 + min(0.45, best * 0.12)

    def register_dance(self, entry: Any) -> dict[str, Any]:
        d = dance_payload(entry)
        eid = d.get("id") or ""
        if eid:
            self.dances[eid] = d
        if d.get("where"):
            self.deposit(list(d["where"]), amount=_DEPOSIT * 0.5)
        return d

    def follow_trails(
        self,
        seed_entities: list[str],
        dances: list[dict[str, Any]],
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Rank other dances by pheromone pull from seed entities (bee/ant)."""
        scored = []
        for d in dances:
            where = d.get("where") or []
            boost = self.trail_boost(seed_entities, where)
            # kind match slight pull (same pollen type)
            scored.append((boost, d))
        scored.sort(key=lambda x: -x[0])
        return [d for b, d in scored[:top_k] if b > 1.02]

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "edges": {a: dict(bs) for a, bs in self.edges.items()},
            "updated": self.updated,
            "dances": self.dances,
            "saved_at": _now(),
        }
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def load(self) -> None:
        if not self.path or not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        self.edges = defaultdict(dict)
        for a, bs in (raw.get("edges") or {}).items():
            self.edges[a] = {str(k): float(v) for k, v in bs.items()}
        self.updated = {str(k): float(v) for k, v in (raw.get("updated") or {}).items()}
        self.dances = dict(raw.get("dances") or {})

    def render_markdown(self) -> str:
        """Human-readable colony board (shared song sheet)."""
        lines = [
            "# Colony board",
            "",
            "_Stigmergy map: ant trails + bee dances inside HermesCube. "
            "Auto-maintained — safe to read; edits may be overwritten._",
            "",
            "## Strong trails",
            "",
        ]
        # flatten unique edges
        seen = set()
        edge_list = []
        now = _now()
        for a, bs in self.edges.items():
            for b, w in bs.items():
                k = self._ekey(a, b)
                if k in seen:
                    continue
                seen.add(k)
                age_h = (now - self.updated.get(k, now)) / 3600.0
                ww = self._evaporate(w, age_h)
                if ww >= 0.4:
                    edge_list.append((ww, a, b))
        edge_list.sort(reverse=True)
        if not edge_list:
            lines.append("_No strong trails yet — use memories to lay scent._")
        else:
            lines.append("| Strength | Node A | Node B |")
            lines.append("|----------|--------|--------|")
            for w, a, b in edge_list[:20]:
                lines.append(f"| {w:.2f} | `{a}` | `{b}` |")
        lines += ["", "## Recent dances (what → where)", ""]
        items = list(self.dances.values())[-15:]
        items.reverse()
        if not items:
            lines.append("_No dances yet._")
        else:
            for d in items:
                where = ", ".join(f"`{x}`" for x in (d.get("where") or [])[:5]) or "—"
                lines.append(
                    f"- **{d.get('kind', '?')}** · `{d.get('id', '')[:8]}` · "
                    f"{d.get('type', '')} → {where}"
                )
        lines.append("")
        return "\n".join(lines)

    def write_markdown_board(self, md_path: str | Path) -> None:
        Path(md_path).parent.mkdir(parents=True, exist_ok=True)
        Path(md_path).write_text(self.render_markdown(), encoding="utf-8")
