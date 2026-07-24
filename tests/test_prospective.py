"""Prospective focus→resolve memory tests."""

from __future__ import annotations

import json
from pathlib import Path

from hermescube import CubeFile
from hermescube.prospective import (
    is_open_focus,
    match_score,
    open_focuses,
    prompt_strip,
    try_close_on_resolve,
)
from hermescube.provider import CubeMemoryProvider


def test_match_and_close(tmp_path: Path):
    c = CubeFile.create(str(tmp_path / "p.cube"))
    f = c.append(
        "focus",
        "Ship HermesCube prospective focus-to-resolve memory loop",
        data={"trust": 0.8},
        outcome="none",
    )
    assert is_open_focus(f)
    assert open_focuses(c.read_l1())
    r = c.append(
        "resolve",
        "Shipped HermesCube prospective focus-to-resolve memory; loop works",
        data={"trust": 0.85},
        outcome="success",
    )
    out = try_close_on_resolve(c, r, min_score=0.15)
    assert out["closed"] is True
    assert out["focus_id"] == f.id
    opens = open_focuses(c.read_l1())
    # original focus still open type-wise unless we filter closed markers;
    # is_open_focus excludes outcome success and prospective_closed markers
    # original remains open unless we check closes_focus_id — open_focuses
    # still sees original focus. Mark original via checking closed markers.
    # Design: original focus stays but we detect close via closed marker.
    # Improve: open_focuses should exclude focuses that have a CLOSED marker.
    c.close()


def test_open_excludes_closed_chain(tmp_path: Path):
    """After close, open_focuses must not re-surface the closed intent."""
    from hermescube.prospective import open_focuses as of

    c = CubeFile.create(str(tmp_path / "p2.cube"))
    f = c.append(
        "focus",
        "Deploy NailLou production to Vercel main",
        data={"trust": 0.8},
    )
    r = c.append(
        "resolve",
        "Deployed NailLou production to Vercel main successfully",
        outcome="success",
        data={"trust": 0.9},
    )
    try_close_on_resolve(c, r, min_score=0.12)
    # patch module open_focuses to respect closed ids — tested after fix
    opens = of(c.read_l1())
    open_ids = {e.id for e in opens}
    # if still open, test documents need fix in open_focuses
    closed_ids = {
        (e.data or {}).get("closes_focus_id")
        for e in c.read_l1()
        if isinstance(e.data, dict) and e.data.get("prospective_closed")
    }
    assert f.id in closed_ids
    assert f.id not in open_ids
    c.close()


def test_provider_intents_and_auto_close(tmp_path: Path):
    hh = str(tmp_path / "h")
    Path(hh, "memories").mkdir(parents=True)
    p = CubeMemoryProvider()
    p.initialize(session_id="pr", hermes_home=hh, platform="cli")
    a = json.loads(
        p.handle_tool_call(
            "hermescube_manage",
            {
                "action": "add",
                "entry_type": "focus",
                "content": "Finish CONTINUITY refresh for HermesCube 0.16 prospective",
            },
        )
    )
    assert a["status"] == "added"
    intents = json.loads(p.handle_tool_call("hermescube_manage", {"action": "intents"}))
    assert intents["status"] == "ok"
    assert intents["prospective"]["open"] >= 1
    r = json.loads(
        p.handle_tool_call(
            "hermescube_manage",
            {
                "action": "add",
                "entry_type": "resolve",
                "outcome": "success",
                "content": "Finished CONTINUITY refresh for HermesCube 0.16 prospective memory",
            },
        )
    )
    assert r.get("prospective", {}).get("closed") is True
    intents2 = json.loads(p.handle_tool_call("hermescube_manage", {"action": "intents"}))
    assert intents2["prospective"]["open"] == 0
    block = p.system_prompt_block()
    # no open intents strip when empty — ok if absent
    p.shutdown()


def test_match_score_basic():
    assert match_score("ship cube prospective", "shipped cube prospective loop") > 0.2
    assert match_score("apple pie recipe", "quantum physics paper") < 0.15
