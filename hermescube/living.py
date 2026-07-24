"""Living archive — chambers (cubes-within-cube) that pulse together.

Vision: HermesCube is not one blob. It is cooperating facets that
catalog, link, improve, and surface memory for any Hermes agent.

Chambers (logical mini-cubes, one warehouse file):
  identity  — peer card / traits / relationships
  doctrine  — wisdom crystals / beliefs
  intent    — open focuses (prospective)
  procedure — forge candidates + drafts
  associate — engram net hubs + colony trails
  narrative — journey + session digests
  catalog   — type/topic index for navigation

pulse() runs each chamber's improve step (cheap, no LLM) and writes
memories/living_state.json so agents see the archive is alive.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_STOP = frozenset(
    "the and for with that this from into your our are was were been have has "
    "not but you they them then than also just about when what who how why "
    "use used using via will can may".split()
)

CHAMBERS = (
    "identity",
    "doctrine",
    "intent",
    "procedure",
    "associate",
    "narrative",
    "catalog",
)


def state_path(hermes_home: str | Path | None = None) -> Path:
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    return hh / "memories" / "living_state.json"


def catalog_path(hermes_home: str | Path | None = None) -> Path:
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    return hh / "memories" / "catalog.json"


def _toks(text: str) -> set[str]:
    out = set()
    for t in _TOKEN.findall(text or ""):
        tl = t.lower()
        if tl not in _STOP and len(tl) >= 3:
            out.add(tl)
    return out


def _chamber_of(entry: Any) -> str:
    et = (getattr(entry, "entry_type", "") or "").lower()
    d = (getattr(entry, "description", "") or "")
    data = getattr(entry, "data", None) or {}
    if not isinstance(data, dict):
        data = {}
    if et in ("trait", "relationship") or data.get("source") == "hermescube_peer_card":
        return "identity"
    if data.get("crystal") or et == "belief":
        return "doctrine"
    if et == "focus" or d.startswith("[CLOSED]"):
        return "intent"
    if (
        data.get("procedure")
        or d.startswith("[PROCEDURE]")
        or d.startswith("[TRAJECTORY]")
        or d.startswith("[PROMOTED]")
    ):
        return "procedure"
    if d.startswith("[SESSION]") or data.get("source") == "session_digest":
        return "narrative"
    if et in ("landmark", "enter", "leave", "epoch_transition"):
        return "narrative"
    if et in ("evolution", "resolve"):
        return "procedure" if data.get("procedure") else "doctrine"
    return "catalog"


def build_catalog(entries: list[Any]) -> dict[str, Any]:
    """Topic + type catalog for navigation (connect dots at index level)."""
    by_type: Counter[str] = Counter()
    by_chamber: Counter[str] = Counter()
    topics: dict[str, list[str]] = defaultdict(list)
    entities: dict[str, int] = Counter()

    for e in entries:
        et = (getattr(e, "entry_type", "") or "unknown").lower()
        by_type[et] += 1
        ch = _chamber_of(e)
        by_chamber[ch] += 1
        desc = (getattr(e, "description", "") or "").strip()
        if not desc or desc.startswith("["):
            continue
        # entity-ish Capitalized tokens / known keys
        for t in re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,}\b", desc):
            if t.lower() not in _STOP:
                entities[t] += 1
        for tok in list(_toks(desc))[:8]:
            if len(topics[tok]) < 5:
                topics[tok].append(str(getattr(e, "id", ""))[:12])

    top_entities = [
        {"name": n, "n": c} for n, c in entities.most_common(40) if c >= 2
    ]
    # topic hubs: tokens that bridge multiple entries
    hubs = sorted(
        ((t, ids) for t, ids in topics.items() if len(ids) >= 3),
        key=lambda x: -len(x[1]),
    )[:30]

    return {
        "v": 1,
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_entries": len(entries),
        "by_type": dict(by_type),
        "by_chamber": dict(by_chamber),
        "entities": top_entities,
        "topic_hubs": [{"topic": t, "n": len(ids), "sample_ids": ids[:5]} for t, ids in hubs],
    }


def connect_dots(
    cube: Any,
    entries: list[Any],
    *,
    max_links: int = 5,
) -> dict[str, Any]:
    """Write soft relationship links when two durable entries share rare entities."""
    stats = {"links": 0, "skipped": 0}
    if cube is None or len(entries) < 4:
        return stats

    # entity → entry ids
    inv: dict[str, list[Any]] = defaultdict(list)
    for e in entries:
        if (getattr(e, "outcome", "") or "") == "superseded":
            continue
        desc = (getattr(e, "description", "") or "").strip()
        if len(desc) < 20 or desc.startswith("["):
            continue
        ents = re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,}\b", desc)
        for ent in ents:
            if ent.lower() in _STOP:
                continue
            inv[ent].append(e)

    # existing link fingerprints
    existing = set()
    for e in entries:
        d = getattr(e, "data", None) or {}
        if isinstance(d, dict) and d.get("dot_link"):
            existing.add(tuple(sorted(d.get("links") or [])))

    written = 0
    for ent, members in sorted(inv.items(), key=lambda x: -len(x[1])):
        if len(members) < 2 or len(members) > 12:
            continue
        # pair first two distinct high-trust-ish
        a, b = members[0], members[1]
        if a.id == b.id:
            continue
        key = tuple(sorted([str(a.id), str(b.id)]))
        if key in existing:
            stats["skipped"] += 1
            continue
        da = (a.description or "")[:80]
        db = (b.description or "")[:80]
        try:
            cube.append(
                entry_type="relationship",
                description=f"[DOT] {ent}: {da} ↔ {db}",
                data={
                    "dot_link": True,
                    "entity": ent,
                    "links": list(key),
                    "source": "living_connect",
                    "trust": 0.62,
                    "chamber": "associate",
                },
                outcome="success",
            )
            existing.add(key)
            written += 1
            stats["links"] = written
            if written >= max_links:
                break
        except Exception as ex:
            logger.debug("connect_dots: %s", ex)
            break
    return stats


def chamber_pulse(
    cube: Any,
    *,
    hermes_home: str | Path | None = None,
    engram: Any = None,
    max_connect: int = 4,
    do_crystalize: bool = True,
    do_peer: bool = True,
) -> dict[str, Any]:
    """One living pulse — all chambers improve the shared archive."""
    report: dict[str, Any] = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chambers": {},
        "ok": False,
    }
    if cube is None:
        report["error"] = "no cube"
        return report

    try:
        entries = list(cube.read_l1() or [])
    except Exception as e:
        report["error"] = str(e)
        return report

    n = len(entries)
    report["entries"] = n

    # --- catalog chamber ---
    try:
        cat = build_catalog(entries)
        cp = catalog_path(hermes_home)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(cat, indent=2), encoding="utf-8")
        report["chambers"]["catalog"] = {
            "n": n,
            "types": cat.get("by_type"),
            "topic_hubs": len(cat.get("topic_hubs") or []),
            "entities": len(cat.get("entities") or []),
            "path": str(cp),
        }
    except Exception as e:
        report["chambers"]["catalog"] = {"error": str(e)}

    # --- doctrine chamber (wisdom crystalize lite) ---
    if do_crystalize and n >= 6:
        try:
            from hermescube.wisdom import crystalize, functional_loop_stats

            st = crystalize(cube, min_cluster=2, max_crystals=4)
            entries = list(cube.read_l1() or [])
            loop = functional_loop_stats(entries)
            report["chambers"]["doctrine"] = {"crystalize": st, "loop": loop}
        except Exception as e:
            report["chambers"]["doctrine"] = {"error": str(e)}
    else:
        report["chambers"]["doctrine"] = {"skipped": True}

    # --- identity chamber ---
    if do_peer and n >= 2:
        try:
            from hermescube.peer_card import refresh_card

            pr = refresh_card(
                entries,
                hermes_home=hermes_home,
                min_interval_s=0,  # pulse always refreshes card
            )
            report["chambers"]["identity"] = {
                "peer": (pr.get("card") or {}).get("peer_name"),
                "path": pr.get("path"),
            }
        except Exception as e:
            report["chambers"]["identity"] = {"error": str(e)}
    else:
        report["chambers"]["identity"] = {"skipped": True}

    # --- intent chamber ---
    try:
        from hermescube.prospective import status as intent_status

        report["chambers"]["intent"] = intent_status(entries)
    except Exception as e:
        report["chambers"]["intent"] = {"error": str(e)}

    # --- procedure chamber ---
    try:
        from hermescube.consent import list_pending
        from hermescube.procedure import list_candidates

        cands = list_candidates(entries, limit=8)
        report["chambers"]["procedure"] = {
            "candidates": len(cands),
            "drafts_pending": len(list_pending(hermes_home)),
        }
    except Exception as e:
        report["chambers"]["procedure"] = {"error": str(e)}

    # --- associate chamber (connect dots + engram hubs) ---
    try:
        dots = connect_dots(cube, entries, max_links=max_connect)
        hubs = []
        if engram is not None and hasattr(engram, "hub_ids"):
            hubs = engram.hub_ids(limit=6)
        report["chambers"]["associate"] = {
            "dot_links": dots.get("links", 0),
            "engram_hubs": hubs[:6],
            "engram": engram.stats() if engram is not None and hasattr(engram, "stats") else {},
        }
    except Exception as e:
        report["chambers"]["associate"] = {"error": str(e)}

    # --- narrative chamber ---
    try:
        from hermescube.journey import read_events, default_paths

        ev = read_events(hermes_home, limit=500)
        sessions = sum(
            1
            for e in entries
            if (getattr(e, "description", "") or "").startswith("[SESSION]")
        )
        jpath, md = default_paths(hermes_home)
        report["chambers"]["narrative"] = {
            "journey_events": len(ev),
            "session_digests": sessions,
            "journey_md": str(md) if Path(md).is_file() else None,
        }
    except Exception as e:
        report["chambers"]["narrative"] = {"error": str(e)}

    # living state snapshot
    report["ok"] = True
    report["alive"] = True
    report["summary"] = _summary_line(report)
    try:
        sp = state_path(hermes_home)
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        report["state_path"] = str(sp)
    except Exception as e:
        report["state_error"] = str(e)

    try:
        from hermescube.journey import log_event

        log_event(
            "living_pulse",
            report.get("summary") or "living pulse",
            hermes_home=hermes_home,
            meta={"links": (report.get("chambers") or {}).get("associate", {}).get("dot_links")},
        )
    except Exception:
        pass

    return report


def _summary_line(report: dict[str, Any]) -> str:
    ch = report.get("chambers") or {}
    parts = [f"entries={report.get('entries')}"]
    if "catalog" in ch and isinstance(ch["catalog"], dict):
        parts.append(f"hubs={ch['catalog'].get('topic_hubs')}")
    if "associate" in ch and isinstance(ch["associate"], dict):
        parts.append(f"dots={ch['associate'].get('dot_links')}")
    if "intent" in ch and isinstance(ch["intent"], dict):
        parts.append(f"open_intents={ch['intent'].get('open')}")
    if "procedure" in ch and isinstance(ch["procedure"], dict):
        parts.append(f"drafts={ch['procedure'].get('drafts_pending')}")
    if "identity" in ch and isinstance(ch["identity"], dict):
        parts.append(f"peer={ch['identity'].get('peer')}")
    return "Living pulse: " + " · ".join(str(p) for p in parts)


def prompt_strip(hermes_home: str | Path | None = None, *, high_load: bool = False) -> str:
    """Compact living-archive face for system prompt."""
    sp = state_path(hermes_home)
    if not sp.is_file():
        return ""
    try:
        st = json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not st.get("ok"):
        return ""
    lines = ["### Living archive (chambers)"]
    lines.append(f"- {st.get('summary') or 'pulse ok'}")
    if high_load:
        return "\n".join(lines)
    ch = st.get("chambers") or {}
    cat = ch.get("catalog") or {}
    if cat.get("by_chamber"):
        bc = cat["by_chamber"]
        parts = [f"{k}:{v}" for k, v in list(bc.items())[:6]]
        lines.append("- Chambers: " + " · ".join(parts))
    assoc = ch.get("associate") or {}
    if assoc.get("dot_links"):
        lines.append(f"- New dot-links last pulse: {assoc.get('dot_links')}")
    return "\n".join(lines)


def load_state(hermes_home: str | Path | None = None) -> dict[str, Any] | None:
    sp = state_path(hermes_home)
    if not sp.is_file():
        return None
    try:
        return json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return None
