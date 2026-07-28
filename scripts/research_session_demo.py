#!/usr/bin/env python3
"""Hermes agent harness × HermesCube — a narrated open-source research session.

This is a synthetic, self-contained walkthrough of how a Hermes agent would use
HermesCube as its long-term memory *and* the grounded self-evolution harness
across a multi-turn research task ("find a good open-source idea to build").

It exercises the real provider + harness code paths — nothing is faked:

  * ``CubeMemoryProvider.initialize`` — open/create the cube memory
  * ``prefetch``                      — recall relevant memory before each turn
  * ``hermescube_manage add``         — write durable beliefs / landmarks / decisions
  * ``hermescube_search`` / ``probe`` — agent-driven recall and entity probes
  * ``hermescube_feedback``           — reinforce a memory that proved useful
  * ``hermescube_manage witness``     — log real friction (ground truth)
  * ``self_evolution`` harness        — predict → evolve → critic → verify → gardener
  * ``hermescube_manage crystalize``  — consolidate near-duplicates into wisdom
  * ``growth`` genealogy              — the cube's living version after the session

Everything writes only under a throwaway ``HERMES_HOME`` (a temp dir by default),
so it never touches a real agent home and commits no user data.

Run:
    python3 scripts/research_session_demo.py
    HERMES_HOME=/tmp/oss_research python3 scripts/research_session_demo.py --keep
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


# ── tiny narration helpers ───────────────────────────────────────────

def hr(char: str = "─", width: int = 74) -> str:
    return char * width


def banner(title: str) -> None:
    print(f"\n{hr('━')}\n  {title}\n{hr('━')}")


def step(label: str) -> None:
    print(f"\n▸ {label}")


def call(provider, tool: str, args: dict) -> dict:
    """Invoke a provider tool call and return the parsed JSON result."""
    raw = provider.handle_tool_call(tool, args)
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw": raw}


def show_recall(provider, query: str, session_id: str) -> None:
    """Prefetch memory the way Hermes does before answering a turn."""
    t0 = time.perf_counter()
    pref = provider.prefetch(query, session_id=session_id) or ""
    ms = (time.perf_counter() - t0) * 1000
    if not pref.strip():
        print(f"    prefetch ({ms:5.2f} ms): (cold — no prior memory yet)")
        return
    lines = [ln for ln in pref.splitlines() if ln.strip()]
    print(f"    prefetch ({ms:5.2f} ms) surfaced {max(0, len(lines) - 1)} memory line(s):")
    for ln in lines[1:6]:
        print(f"      · {ln.strip()[:96]}")


# ── the research session ─────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--keep",
        action="store_true",
        help="Keep the temp HERMES_HOME after the run (default: clean up)",
    )
    args = ap.parse_args()

    # Isolated home — never a real agent tree.
    tmp_home = None
    home = os.environ.get("HERMES_HOME")
    if not home:
        tmp_home = tempfile.mkdtemp(prefix="hermescube_oss_research_")
        home = tmp_home
    os.environ["HERMES_HOME"] = home

    from hermescube import __version__
    from hermescube import self_evolution as se
    from hermescube.provider import CubeMemoryProvider

    sid = time.strftime("oss-research-%Y%m%dT%H%M%SZ", time.gmtime())

    banner(f"Hermes agent harness × HermesCube v{__version__}")
    print(f"  session: {sid}")
    print(f"  HERMES_HOME: {home}")
    print("  task: research and pick an open-source project idea worth building")

    provider = CubeMemoryProvider()
    provider.initialize(
        session_id=sid,
        hermes_home=home,
        platform="cli",
        agent_context="primary",
    )
    print(f"  cube: {provider._cube_path}  (entries before: {provider._cube.entry_count})")

    stored: dict[str, str] = {}

    def remember(entry_type: str, content: str, outcome: str = "none") -> str:
        a = {"action": "add", "entry_type": entry_type, "content": content}
        if outcome != "none":
            a["outcome"] = outcome
        r = call(provider, "hermescube_manage", a)
        eid = r.get("id", "")
        if eid:
            stored[content[:40]] = eid
        print(f"    +remember [{entry_type}"
              f"{('/' + outcome) if outcome != 'none' else ''}] "
              f"{content[:70]}  → {eid or r}")
        return eid

    # ── TURN 1 — frame the research ─────────────────────────────────
    banner("TURN 1 — What makes a good open-source idea?")
    u1 = "I want to build an open-source project. What makes a good idea?"
    show_recall(provider, u1, sid)
    a1 = ("Strong OSS ideas usually: (1) scratch a real recurring itch the "
          "author has, (2) have a narrow, sharp v1 scope, (3) sit in a niche "
          "big vendors ignore, and (4) are easy to try in under 5 minutes.")
    print(f"  user>  {u1}")
    print(f"  agent> {a1}")
    remember("belief", "Good OSS ideas scratch the author's own recurring itch first", "none")
    remember("belief", "A sharp, narrow v1 scope beats a broad roadmap for OSS adoption", "none")
    remember("trait", "I evaluate OSS ideas on: real itch, narrow scope, niche gap, 5-min try", "none")
    provider.sync_turn(u1, a1, session_id=sid)

    # ── TURN 2 — survey candidate ideas ─────────────────────────────
    banner("TURN 2 — Survey candidate ideas")
    u2 = "Give me a few concrete candidate ideas in developer tooling."
    show_recall(provider, u2, sid)
    a2 = ("Candidates: (A) a local-first semantic changelog generator, "
          "(B) a CLI that turns flaky test logs into minimal repros, "
          "(C) an offline embedding-free memory store for agents.")
    print(f"  user>  {u2}")
    print(f"  agent> {a2}")
    remember("landmark", "Candidate A: local-first semantic changelog generator", "none")
    remember("landmark", "Candidate B: CLI turning flaky test logs into minimal repros", "none")
    remember("landmark", "Candidate C: offline embedding-free memory store for agents", "none")
    remember("relationship", "Candidate C competes-with hosted vector databases", "none")
    provider.sync_turn(u2, a2, session_id=sid)

    # ── TURN 3 — friction: a claim didn't hold up (witness) ─────────
    banner("TURN 3 — Reality check (real friction → witness ledger)")
    u3 = "Wait, isn't 'offline embedding-free memory' already crowded?"
    show_recall(provider, u3, sid)
    a3 = ("Correction: my earlier framing was too rosy. Most 'offline memory' "
          "tools still call an embedding API. The genuinely embedding-free "
          "niche is thin — that's the real gap, not a crowded space.")
    print(f"  user>  {u3}")
    print(f"  agent> {a3}")
    step("The agent hit friction (it had to correct itself) — log it as ground truth")
    wr = call(provider, "hermescube_manage", {
        "action": "witness",
        "content": ("Over-claimed that offline agent memory is crowded; the "
                    "embedding-free slice is actually under-served"),
        "severity": "medium",
    })
    print(f"    witness recorded: {wr.get('recorded', wr)}")
    provider.sync_turn(u3, a3, session_id=sid)

    # ── TURN 4 — decide, and commit a falsifiable prediction ────────
    banner("TURN 4 — Decision + falsifiable prediction")
    u4 = "Okay, pick one and commit."
    show_recall(provider, u4, sid)
    a4 = ("Decision: build Candidate C — an offline, embedding-free memory "
          "store for agents — because it maps to a real under-served niche "
          "and has a 5-minute 'init → append → query' first run.")
    print(f"  user>  {u4}")
    print(f"  agent> {a4}")
    decision_id = remember(
        "resolve",
        "DECIDED: build an offline, embedding-free agent memory store (Candidate C)",
        "success",
    )
    step("Commit falsifiable predictions with expiries (grounded self-evolution)")
    pred = se.make_prediction(
        home,
        "The 'embedding-free niche' framing will not be contradicted by new friction this week",
        check={"type": "witness_absence", "pattern": "embedding-free"},
        horizon_days=7.0,
        source=sid,
    )
    print(f"    prediction (7d): {pred['id']}  status={pred['status']}  check={pred['check']}")
    time.sleep(0.002)  # distinct millisecond-based id from the 7d prediction
    # A short intra-cycle check the verifier can settle now: the decision framing
    # held for the rest of this session (no *new* embedding-free friction after it).
    pred_now = se.make_prediction(
        home,
        "No new 'embedding-free' friction surfaced after committing the decision this session",
        check={"type": "witness_absence", "pattern": "embedding-free"},
        horizon_days=0.0,
        source=sid,
    )
    print(f"    prediction (intra-cycle): {pred_now['id']}  status={pred_now['status']}")
    provider.sync_turn(u4, a4, session_id=sid)

    # ── Agent-driven recall: search + probe + feedback ──────────────
    banner("Agent-driven recall — search, probe, feedback")
    step("hermescube_search: 'which open source idea did we pick and why'")
    sr = call(provider, "hermescube_search",
              {"query": "which open source idea did we pick and why", "top_k": 5})
    for h in (sr.get("results") or [])[:5]:
        print(f"    {h.get('score', 0):.3f} [{h.get('type')}] {(h.get('description') or '')[:72]}")

    step("hermescube_probe: entity 'embedding-free memory'")
    pr = call(provider, "hermescube_probe",
              {"action": "related", "entity": "embedding-free memory", "limit": 4})
    for h in (pr.get("results") or [])[:4]:
        print(f"    {h.get('score', 0):.3f} [{h.get('type')}] {(h.get('description') or '')[:72]}")

    if decision_id:
        step("hermescube_feedback: the decision memory was helpful → reinforce trust")
        fb = call(provider, "hermescube_feedback",
                  {"action": "helpful", "entry_id": decision_id})
        print(f"    feedback: {fb}")

    # ── Harness: evolve → critic → verify → gardener ────────────────
    banner("Self-evolution harness — evolve → critic → verify → gardener")

    step("Grounded evolve cycle (witness-anchored; every cycle is logged)")
    try:
        ev = se.run_grounded_evolve(provider, label="session_end")
        cyc = ev.get("cycle") or {}
        print(f"    cycle {cyc.get('cycle_id')}  outcome={cyc.get('outcome')}  "
              f"ok={ev.get('ok')}  open_witnesses={cyc.get('detail', {}).get('open_witnesses')}")
    except Exception as e:
        # Fall back to the provider's offline consolidation if branch evolve is unavailable
        print(f"    (branched evolve unavailable: {e}; using evolve_consolidated)")
        ev = provider.evolve_consolidated()
        print(f"    consolidation: { {k: ev.get(k) for k in ('phase', 'clusters', 'deduped')} }")

    step("Verifier settles falsifiable predictions (verdicts are permanent)")
    ver = call(provider, "hermescube_manage", {"action": "harness", "harness_action": "verify"})
    print(f"    open={ver.get('open')} confirmed={ver.get('confirmed')} "
          f"refuted={ver.get('refuted')} expired={ver.get('expired')}")

    step("Critic (mechanical, anti-collusion) reviews recent cycles + predictions")
    crit = call(provider, "hermescube_manage", {"action": "harness", "harness_action": "critic"})
    print(f"    verdict={crit.get('verdict')}  cycles_reviewed={crit.get('cycles_reviewed')}  "
          f"open_witnesses={crit.get('open_witnesses')}")
    for f in crit.get("findings") or []:
        print(f"      ! {f.get('flag')}: {f.get('detail')}")

    step("Gardener surfaces dormant durable memories (proposes, never deletes)")
    gard = call(provider, "hermescube_manage", {"action": "harness", "harness_action": "gardener"})
    print(f"    durable_scanned={gard.get('durable_scanned')}  "
          f"dormant_candidates={len(gard.get('dormant_candidates') or [])}")

    step("Harness status roll-up")
    hs = call(provider, "hermescube_manage", {"action": "harness", "harness_action": "status"})
    print(f"    open_witnesses={hs.get('open_witnesses')}  predictions={hs.get('predictions')}")

    # ── Consolidate wisdom + living growth ──────────────────────────
    banner("Consolidation + living growth")
    step("Crystalize near-duplicate memories into belief crystals")
    cr = call(provider, "hermescube_manage", {"action": "crystalize"})
    print(f"    crystals={cr.get('stats', {}).get('crystals')}  "
          f"candidates={cr.get('stats', {}).get('candidates')}  loop={cr.get('loop')}")

    step("Living cube genealogy after the session")
    gr = call(provider, "hermescube_manage", {"action": "growth", "content": "status"})
    age = gr.get("age") or {}
    print(f"    living version v{gr.get('version')}  era={gr.get('era_label') or gr.get('era')}  "
          f"capability={gr.get('capability', gr.get('strength'))}/100")
    print(f"    age={age.get('label', '—')}  diary={gr.get('cube_md')}")

    # ── Fresh-session recall: proof the memory compounded ───────────
    banner("Proof of compounding — a brand-new session recalls the decision")
    provider.shutdown()
    sid2 = sid + "-followup"
    p2 = CubeMemoryProvider()
    p2.initialize(session_id=sid2, hermes_home=home, platform="cli", agent_context="primary")
    followup = "Remind me: what open-source project did I decide to build, and why?"
    print(f"  user>  {followup}")
    recall = p2.prefetch(followup, session_id=sid2) or ""
    for ln in [ln for ln in recall.splitlines() if ln.strip()][:6]:
        print(f"    · {ln.strip()[:96]}")
    integ = p2._cube.integrity_check()
    entries_final = p2._cube.entry_count
    p2.shutdown()

    banner("Session summary")
    print(f"  entries in cube:     {entries_final}")
    print(f"  integrity ok:        {integ.get('ok')} "
          f"(empty={integ.get('empty_descriptions')}, dups={integ.get('duplicate_ids')}, "
          f"bad_vec={integ.get('bad_vectors')})")
    print(f"  witnesses / preds:   {hs.get('open_witnesses')} open witness(es), "
          f"{hs.get('predictions')}")
    print(f"  decision memory id:  {decision_id}")

    if tmp_home is not None and not args.keep:
        import shutil
        shutil.rmtree(tmp_home, ignore_errors=True)
        print(f"\n  (cleaned up temp home {tmp_home}; pass --keep to retain)")
    else:
        print(f"\n  (kept HERMES_HOME at {home})")

    ok = bool(integ.get("ok")) and entries_final > 0
    print("\nRESEARCH_SESSION_OK" if ok else "\nRESEARCH_SESSION_PARTIAL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
