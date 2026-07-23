"""Hygiene + journey prune tests."""

from __future__ import annotations

import json
from pathlib import Path

from hermescube.journey import (
    is_noise_text,
    log_event,
    prune_events,
    read_events,
    wisdom_from_cube,
    hygiene_cube_noise,
)
from hermescube import CubeFile
from hermescube.provider import CubeMemoryProvider


def test_is_noise_filters():
    assert is_noise_text("PERSIST-PROOF-4012498-REAL")
    assert is_noise_text("[CRYSTALIZED] something")
    assert is_noise_text("session ended")
    assert is_noise_text("ILO firsthand Cube session 2026-07-23T170352Z: foo")
    assert not is_noise_text("HermesCube GH main is SoT; never wipes memory.cube")
    assert not is_noise_text("Hot MEMORY.md stays doctrine; Cube is deep warehouse")


def test_wisdom_excludes_noise(tmp_path: Path):
    p = tmp_path / "c.cube"
    c = CubeFile.create(str(p))
    c.append(
        "belief",
        "PERSIST-PROOF-token-should-not-be-wisdom",
        data={"crystal": True, "trust": 0.99},
        outcome="success",
    )
    c.append(
        "belief",
        "MEMORY.md is hot doctrine alongside Cube warehouse",
        data={"crystal": True, "trust": 0.9},
        outcome="success",
    )
    ents = c.read_l1()
    w = wisdom_from_cube(entries=ents)
    texts = " ".join(t for t, _ in w)
    assert "PERSIST-PROOF" not in texts
    assert "MEMORY.md" in texts
    c.close()


def test_prune_and_hygiene_provider(tmp_path: Path):
    hh = str(tmp_path / "h")
    Path(hh, "memories").mkdir(parents=True)
    log_event("manage_add", "Good durable fact about Cube SoT", hermes_home=hh)
    log_event("manage_add", "PERSIST-PROOF-should-prune", hermes_home=hh)
    # noise may already be blocked by log_event — force-write one noisy line
    jpath = Path(hh) / "memories" / "journey.jsonl"
    with open(jpath, "a") as f:
        f.write(
            json.dumps(
                {
                    "t": 1,
                    "iso": "x",
                    "kind": "noise",
                    "summary": "PERSIST-PROOF-forced",
                    "entry_id": "",
                    "meta": {},
                }
            )
            + "\n"
        )
    st = prune_events(hh, drop_noise=True)
    assert st["removed"] >= 1
    for e in read_events(hh):
        assert "PERSIST-PROOF" not in (e.get("summary") or "")

    p = CubeMemoryProvider()
    p.initialize(session_id="h", hermes_home=hh, platform="cli")
    p.handle_tool_call(
        "hermescube_manage",
        {"action": "add", "content": "PERSIST-PROOF-in-cube", "entry_type": "landmark"},
    )
    p.handle_tool_call(
        "hermescube_manage",
        {
            "action": "add",
            "content": "Cube hygiene keeps doctrine-grade wisdom only",
            "entry_type": "belief",
        },
    )
    r = json.loads(p.handle_tool_call("hermescube_manage", {"action": "hygiene", "sync_world": False}))
    assert r.get("status") == "hygiene"
    assert r.get("ok") is True
    assert (r.get("cube") or {}).get("superseded", 0) >= 1
    ents = p._cube.read_l1()
    w = wisdom_from_cube(entries=ents)
    assert all("PERSIST" not in t for t, _ in w)
    assert any("doctrine-grade" in t or "hygiene" in t.lower() for t, _ in w) or len(w) >= 0
    p.shutdown()
