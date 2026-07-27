"""Nexus — functional memory infrastructure inside HermesCube.

The cube is one warehouse file, but it needs *infrastructure*:
  SPACE      — vaults + chambers (organization without a second store)
  CONNECTIONS — unified neighbors across SPO / colony / engram
  PROGRESS   — append-only ledger proving the loop improved usefulness

This module does not replace genealogy, relations, colony, or triage.
It is the spine that makes them one navigable system for agents.
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────


def progress_path(
    hermes_home: str | Path | None = None,
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> Path:
    from hermescube.framework.paths import resolve_cube_paths

    return resolve_cube_paths(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    ).progress_ledger


def nexus_state_path(
    hermes_home: str | Path | None = None,
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> Path:
    from hermescube.framework.paths import resolve_cube_paths

    return resolve_cube_paths(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    ).nexus_state


# ── SPACE ────────────────────────────────────────────────────────────


def space_map(
    cube: Any,
    *,
    hermes_home: str | Path | None = None,
    active_vault: str = "",
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Organization map: chambers + vaults + density — one warehouse, many rooms."""
    from hermescube.living import CHAMBERS, _chamber_of

    entries = list(cube.read_l1() or []) if cube is not None else []
    chamber_counts: Counter[str] = Counter()
    vault_counts: Counter[str] = Counter()
    labeled = 0
    for e in entries:
        chamber_counts[_chamber_of(e)] += 1
        d = e.data if isinstance(getattr(e, "data", None), dict) else {}
        v = str(d.get("vault") or "").strip()
        if v:
            vault_counts[v] += 1
            labeled += 1
        else:
            vault_counts["(unlabeled)"] += 1

    catalog = {}
    try:
        from hermescube.living import build_catalog as _bc

        catalog = _bc(entries) or {}
    except Exception as ex:
        logger.debug("catalog skip: %s", ex)

    vaults = [
        {"vault": name, "entries": n, "active": name == (active_vault or "")}
        for name, n in vault_counts.most_common(24)
    ]
    chambers = [
        {"chamber": c, "entries": int(chamber_counts.get(c, 0))}
        for c in CHAMBERS
    ]
    topics_raw = catalog.get("topics") or {}
    if isinstance(topics_raw, dict):
        topic_list = sorted(topics_raw.keys(), key=lambda k: -len(topics_raw.get(k) or []))[:12]
    elif isinstance(topics_raw, list):
        topic_list = topics_raw[:12]
    else:
        topic_list = []
    return {
        "ok": True,
        "entries": len(entries),
        "labeled_vault": labeled,
        "unlabeled": int(vault_counts.get("(unlabeled)", 0)),
        "active_vault": active_vault or "",
        "agent_identity": agent_identity or "",
        "agent_workspace": agent_workspace or "",
        "chambers": chambers,
        "vaults": vaults,
        "topics": topic_list,
        "types": dict(catalog.get("by_type") or catalog.get("types") or {}),
    }


def chamber_filter_ids(cube: Any, chamber: str, *, limit: int = 80) -> list[str]:
    """Entry ids belonging to a logical chamber (for scoped recall)."""
    from hermescube.living import _chamber_of

    want = (chamber or "").strip().lower()
    if not want or cube is None:
        return []
    out: list[str] = []
    for e in list(cube.read_l1() or []):
        if _chamber_of(e) == want:
            out.append(str(e.id))
            if len(out) >= limit:
                break
    return out


# ── CONNECTIONS ──────────────────────────────────────────────────────


def connect_entity(
    entity: str,
    *,
    cube: Any = None,
    hermes_home: str | Path | None = None,
    relation_store: Any = None,
    colony: Any = None,
    engram: Any = None,
    engine: Any = None,
    limit: int = 12,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Unified neighbor view: SPO + colony trails + engram hubs + HAR related.

    One pane for "what connects to X" — the infrastructure agents need
    when memory is more than a bag of facts.
    """
    entity = (entity or "").strip()
    if not entity:
        return {"ok": False, "error": "entity required"}

    spo: list[dict[str, Any]] = []
    try:
        if relation_store is None and hermes_home:
            from hermescube.relations import RelationStore

            relation_store = RelationStore(
                hermes_home,
                agent_identity=agent_identity,
                agent_workspace=agent_workspace,
                nest_profiles=nest_profiles,
            )
        if relation_store is not None:
            spo = [r.to_dict() for r in relation_store.query(entity, limit=limit)]
    except Exception as e:
        logger.debug("connect SPO skip: %s", e)

    trails: list[dict[str, Any]] = []
    try:
        if colony is not None:
            seeds = [entity.lower()]
            dances = list(getattr(colony, "dances", None) or [])
            trails = colony.follow_trails(seeds, dances, top_k=limit) if dances else []
            # Also surface direct pheromone neighbors
            edges = getattr(colony, "edges", {}) or {}
            bucket = edges.get(entity.lower()) or {}
            for nbr, w in sorted(bucket.items(), key=lambda x: -float(x[1]))[:limit]:
                trails.append({"where": [nbr], "pheromone": round(float(w), 4), "kind": "edge"})
    except Exception as e:
        logger.debug("connect colony skip: %s", e)

    hubs: list[dict[str, Any]] = []
    try:
        if engram is not None and cube is not None:
            by_id = {str(e.id): e for e in list(cube.read_l1() or [])}
            for hid in engram.hub_ids(limit=limit):
                e = by_id.get(str(hid))
                if e is None:
                    continue
                desc = (e.description or "")[:160]
                ents = (e.data or {}).get("entities") if isinstance(e.data, dict) else []
                if entity.lower() in desc.lower() or any(
                    entity.lower() == str(x).lower() for x in (ents or [])
                ):
                    hubs.append(
                        {
                            "entry_id": str(e.id),
                            "type": e.entry_type,
                            "description": desc,
                            "source": "engram_hub",
                        }
                    )
    except Exception as e:
        logger.debug("connect engram skip: %s", e)

    related: list[dict[str, Any]] = []
    try:
        if engine is not None and hasattr(engine, "related"):
            hits = engine.related(entity, top_k=limit) or []
            for h in hits:
                if isinstance(h, tuple) and len(h) >= 1:
                    entry, score = h[0], float(h[1] if len(h) > 1 else 0)
                    related.append(
                        {
                            "entry_id": str(getattr(entry, "id", "")),
                            "type": getattr(entry, "entry_type", ""),
                            "description": (getattr(entry, "description", "") or "")[:160],
                            "score": round(score, 4),
                            "source": "har_related",
                        }
                    )
                elif isinstance(h, dict):
                    related.append({**h, "source": h.get("source") or "har_related"})
    except Exception as e:
        logger.debug("connect HAR related skip: %s", e)

    return {
        "ok": True,
        "entity": entity,
        "spo": spo[:limit],
        "colony": trails[:limit],
        "engram_hubs": hubs[:limit],
        "related": related[:limit],
        "counts": {
            "spo": len(spo),
            "colony": len(trails),
            "engram_hubs": len(hubs),
            "related": len(related),
        },
    }


def bridge_claim_to_relation(
    claim: Any,
    store: Any,
    *,
    expire_superseded: bool = True,
) -> dict[str, Any]:
    """Project a Claim into the SPO store (bi-temporal when fields exist)."""
    if store is None or claim is None:
        return {"ok": False, "error": "claim and store required"}
    try:
        d = claim.to_dict() if hasattr(claim, "to_dict") else dict(claim)
    except Exception:
        d = {}
    subj = str(d.get("subject") or d.get("entity") or "").strip()
    pred = str(d.get("predicate") or d.get("relation") or "claims").strip()
    obj = str(d.get("object") or d.get("value") or d.get("statement") or "").strip()
    if not obj and d.get("text"):
        obj = str(d["text"])[:200]
    if not subj or not obj:
        # Fall back: treat statement as object under generic subject
        text = str(d.get("text") or d.get("statement") or "").strip()
        if not text:
            return {"ok": False, "error": "claim missing subject/object"}
        subj = subj or "memory"
        pred = pred or "asserts"
        obj = text[:200]
    mid = str(d.get("memory_id") or d.get("entry_id") or d.get("id") or "") or None
    valid_from = d.get("valid_from") or d.get("t_valid_from")
    valid_to = d.get("valid_to") or d.get("t_valid_to")
    try:
        if expire_superseded and d.get("supersedes"):
            # Soft-expire prior claim targets when provided as SPO triples
            prior = d.get("supersedes")
            if isinstance(prior, dict):
                store.expire(
                    str(prior.get("subject") or subj),
                    str(prior.get("predicate") or pred),
                    str(prior.get("object") or ""),
                )
        rel = store.record(
            subj,
            pred,
            obj,
            valid_from=str(valid_from) if valid_from else None,
            valid_to=str(valid_to) if valid_to else None,
            memory_id=mid,
        )
        return {"ok": True, "relation": rel.to_dict()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── PROGRESS ─────────────────────────────────────────────────────────


def record_progress(
    hermes_home: str | Path | None,
    kind: str,
    *,
    detail: str = "",
    metrics: dict[str, Any] | None = None,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Append one progress event — proof the compounding loop moved."""
    p = progress_path(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": time.time(),
        "kind": (kind or "tick").strip()[:64],
        "detail": (detail or "")[:400],
        "metrics": metrics or {},
    }
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    return {"ok": True, **rec, "path": str(p)}


def progress_status(
    hermes_home: str | Path | None,
    *,
    cube: Any = None,
    limit: int = 20,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Rollup: recent ledger + growth snapshot + functional loop health."""
    pkw = dict(
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    p = progress_path(hermes_home, **pkw)
    events: list[dict[str, Any]] = []
    kinds: Counter[str] = Counter()
    if p.is_file():
        try:
            lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
            for ln in lines[-max(1, limit * 3) :]:
                try:
                    rec = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    events.append(rec)
                    kinds[str(rec.get("kind") or "?")] += 1
        except OSError:
            pass
    recent = events[-limit:]

    growth: dict[str, Any] = {}
    try:
        from hermescube.genealogy import growth_status

        growth = growth_status(hermes_home, cube=cube)
    except Exception:
        growth = {}

    loop: dict[str, Any] = {}
    try:
        if cube is not None:
            from hermescube.wisdom import functional_loop_stats

            loop = functional_loop_stats(list(cube.read_l1() or []))
    except Exception:
        loop = {}

    # Usefulness: helpful feedback rate from ledger metrics if present
    helpful = 0
    unhelpful = 0
    for e in events:
        m = e.get("metrics") or {}
        helpful += int(m.get("helpful") or 0)
        unhelpful += int(m.get("unhelpful") or 0)
    usefulness = None
    if helpful + unhelpful > 0:
        usefulness = round(helpful / (helpful + unhelpful), 3)

    return {
        "ok": True,
        "path": str(p),
        "events": len(events),
        "kinds": dict(kinds),
        "recent": recent,
        "usefulness": usefulness,
        "growth": {
            "version": growth.get("version"),
            "era": growth.get("era"),
            "era_label": growth.get("era_label"),
            "capability": growth.get("capability") or growth.get("strength"),
            "cycles": (growth.get("age") or {}).get("cycles")
            if isinstance(growth.get("age"), dict)
            else growth.get("cycles"),
        },
        "loop": loop,
    }


# ── TRIAGE APPLY ─────────────────────────────────────────────────────


def apply_triage(
    cube: Any,
    hermes_home: str | Path | None,
    *,
    plan: dict[str, Any] | None = None,
    forge_limit: int = 2,
    annotate_limit: int = 6,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Execute a triage plan — make queues *do* work, not only advise."""
    from hermescube.triage import load_plan, run_triage

    pkw = dict(
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    if plan is None:
        plan = load_plan(hermes_home, **pkw) or run_triage(
            cube, hermes_home=hermes_home, per_route_limit=8, **pkw
        )

    report: dict[str, Any] = {
        "ok": True,
        "forged": 0,
        "annotated": 0,
        "actions": [],
    }
    queues = plan.get("queues") or plan.get("routes") or {}
    if not isinstance(queues, dict):
        queues = {}

    # consolidate → forge (capped)
    consolidate = list(queues.get("consolidate") or [])
    if consolidate and cube is not None:
        try:
            from hermescube.procedure import forge

            r = forge(
                cube,
                hermes_home=hermes_home,
                limit=min(forge_limit, max(1, len(consolidate))),
                write_drafts=True,
            )
            forged_n = len(r.get("forged") or []) if isinstance(r, dict) else 0
            report["forged"] = forged_n
            report["actions"].append({"route": "consolidate", "result": r})
        except Exception as e:
            report["actions"].append({"route": "consolidate", "error": str(e)})

    # reconsolidate → conflict scan + soft annotate
    recon = list(queues.get("reconsolidate") or [])[: max(0, annotate_limit)]
    if recon and cube is not None:
        try:
            from hermescube.conflict import find_conflicts, annotate_conflicts

            entries = list(cube.read_l1() or [])
            by_id = {str(e.id): e for e in entries}
            subset = [
                by_id[str(c.get("item_id") or c.get("id") or c.get("entry_id"))]
                for c in recon
                if str(c.get("item_id") or c.get("id") or c.get("entry_id") or "") in by_id
            ]
            if len(subset) >= 2:
                conflicts = find_conflicts(subset) or []
                n = 0
                # annotate against the first entry as "new" for each conflict pair
                if conflicts and subset:
                    n = annotate_conflicts(cube, subset[0], conflicts)
                report["annotated"] = int(n or 0)
                report["actions"].append(
                    {
                        "route": "reconsolidate",
                        "conflicts": len(conflicts),
                        "annotated": report["annotated"],
                    }
                )
            else:
                report["actions"].append(
                    {"route": "reconsolidate", "note": "need ≥2 entries in queue"}
                )
        except Exception as e:
            report["actions"].append({"route": "reconsolidate", "error": str(e)})

    if hermes_home:
        record_progress(
            hermes_home,
            "triage_apply",
            detail=f"forged={report['forged']} annotated={report['annotated']}",
            metrics={"forged": report["forged"], "annotated": report["annotated"]},
            **pkw,
        )
    return report


# ── NEXUS STATUS / PROMPT ────────────────────────────────────────────


def nexus_status(
    cube: Any,
    hermes_home: str | Path | None,
    *,
    active_vault: str = "",
    colony: Any = None,
    engram: Any = None,
    relation_store: Any = None,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Single pane: space + connections density + progress."""
    pkw = dict(
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    space = space_map(
        cube,
        hermes_home=hermes_home,
        active_vault=active_vault,
        **pkw,
    )
    progress = progress_status(hermes_home, cube=cube, **pkw)

    rel_stats: dict[str, Any] = {}
    try:
        if relation_store is None and hermes_home:
            from hermescube.relations import RelationStore

            relation_store = RelationStore(hermes_home, **pkw)
        if relation_store is not None:
            rel_stats = relation_store.stats()
    except Exception:
        rel_stats = {}

    colony_n = 0
    try:
        if colony is not None:
            colony_n = sum(len(v) for v in (getattr(colony, "edges", {}) or {}).values()) // 2
    except Exception:
        colony_n = 0

    engram_n = 0
    try:
        if engram is not None:
            engram_n = len(getattr(engram, "_edges", {}) or {})
    except Exception:
        engram_n = 0

    status = {
        "ok": True,
        "space": space,
        "connections": {
            "relations": rel_stats.get("relations", 0),
            "relations_open": rel_stats.get("open", 0),
            "colony_edges": colony_n,
            "engram_nodes": engram_n,
        },
        "progress": {
            "events": progress.get("events", 0),
            "kinds": progress.get("kinds", {}),
            "usefulness": progress.get("usefulness"),
            "growth": progress.get("growth", {}),
            "loop": progress.get("loop", {}),
        },
    }

    # Persist snapshot for agents / doctor
    if hermes_home:
        try:
            sp = nexus_state_path(hermes_home, **pkw)
            sp.parent.mkdir(parents=True, exist_ok=True)
            snap = {"ts": time.time(), **status}
            sp.write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")
            status["state_path"] = str(sp)
        except OSError as e:
            logger.debug("nexus state write skip: %s", e)

    return status


def prompt_strip(
    hermes_home: str | Path | None = None,
    *,
    cube: Any = None,
    active_vault: str = "",
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> str:
    """One-line infrastructure strip for the system prompt."""
    try:
        st = nexus_status(
            cube,
            hermes_home,
            active_vault=active_vault,
            agent_identity=agent_identity,
            agent_workspace=agent_workspace,
            nest_profiles=nest_profiles,
        )
    except Exception:
        return ""
    space = st.get("space") or {}
    conn = st.get("connections") or {}
    prog = st.get("progress") or {}
    g = prog.get("growth") or {}
    n_ch = sum(int(c.get("entries") or 0) for c in (space.get("chambers") or []))
    vault = active_vault or "(shared)"
    return (
        f"Nexus infra · vault={vault} · chambers={n_ch} entries · "
        f"SPO={conn.get('relations', 0)} colony={conn.get('colony_edges', 0)} "
        f"engram={conn.get('engram_nodes', 0)} · "
        f"progress events={prog.get('events', 0)} · "
        f"living v{g.get('version') or '?'} {g.get('era_label') or ''}"
    ).strip()
