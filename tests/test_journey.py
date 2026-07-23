"""Journey ledger + Hermespace world bridge tests."""

from __future__ import annotations

import json
from pathlib import Path

from hermescube.journey import (
    log_event,
    read_events,
    render_markdown,
    write_markdown,
    wisdom_from_cube,
)
from hermescube import CubeFile
from hermescube.provider import CubeMemoryProvider


def test_journey_log_and_render(tmp_path: Path):
    hh = tmp_path / "h"
    (hh / "memories").mkdir(parents=True)
    log_event("manage_add", "HermesCube journey test fact", hermes_home=hh, entry_id="abc")
    log_event("session ended", "session ended", hermes_home=hh)  # should skip noise if filtered
    ev = read_events(hh)
    assert any(e.get("kind") == "manage_add" for e in ev)
    md = render_markdown(hh)
    assert "HermesCube Journey" in md
    assert "journey test fact" in md
    path = write_markdown(hh)
    assert path.is_file()


def test_provider_journey_action(tmp_path: Path):
    hh = str(tmp_path / "hh")
    Path(hh, "memories").mkdir(parents=True)
    p = CubeMemoryProvider()
    p.initialize(session_id="j", hermes_home=hh, platform="cli")
    p.handle_tool_call(
        "hermescube_manage",
        {"action": "add", "entry_type": "belief", "content": "Journey records material learning events"},
    )
    # near dups for crystal
    p.handle_tool_call(
        "hermescube_manage",
        {"action": "add", "entry_type": "belief", "content": "Journey ledger records material learn events"},
    )
    r = json.loads(p.handle_tool_call("hermescube_manage", {"action": "journey"}))
    assert r.get("status") == "ok"
    assert "markdown" in r
    assert Path(hh, "memories", "journey.md").is_file() or r.get("events") is not None
    # events from manage_add
    assert any(e.get("kind") == "manage_add" for e in (r.get("events") or []))
    p.shutdown()


def test_wisdom_from_cube_crystals(tmp_path: Path):
    path = tmp_path / "c.cube"
    c = CubeFile.create(str(path))
    c.append(
        "belief",
        "Cube crystals are active wisdom",
        data={"crystal": True, "trust": 0.9, "source": "wisdom_crystalizer"},
        outcome="success",
    )
    c.close()
    w = wisdom_from_cube(path)
    assert w and "crystals" in w[0][0].lower()
