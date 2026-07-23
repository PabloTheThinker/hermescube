"""Procedure forge tests."""

from __future__ import annotations

import json
from pathlib import Path

from hermescube import CubeFile
from hermescube.procedure import forge, is_procedure_candidate, list_candidates, list_drafts
from hermescube.provider import CubeMemoryProvider


def test_candidate_detect_and_forge(tmp_path: Path):
    p = tmp_path / "c.cube"
    c = CubeFile.create(str(p))
    e1 = c.append(
        "resolve",
        "Always run hermescube doctor after plugin update; never wipe memory.cube",
        data={"trust": 0.9, "source": "hermescube_manage"},
        outcome="success",
    )
    c.append(
        "landmark",
        "ok",
        data={"trust": 0.2},
        outcome="none",
    )
    ents = c.read_l1()
    assert is_procedure_candidate(e1)
    cands = list_candidates(ents)
    assert any(x.id == e1.id for x in cands)

    hh = tmp_path / "h"
    (hh / "memories").mkdir(parents=True)
    stats = forge(c, hermes_home=hh, limit=5, write_drafts=True)
    assert stats["forged"] >= 1
    assert stats["drafts"]
    assert Path(stats["drafts"][0]).is_file()
    text = Path(stats["drafts"][0]).read_text()
    assert "Draft" in text and "never wipe" in text.lower() or "memory.cube" in text
    # second forge should not duplicate same source
    stats2 = forge(c, hermes_home=hh, limit=5, write_drafts=True)
    assert stats2["forged"] == 0
    c.close()


def test_provider_forge_action(tmp_path: Path):
    hh = str(tmp_path / "hh")
    Path(hh, "memories").mkdir(parents=True)
    p = CubeMemoryProvider()
    p.initialize(session_id="f", hermes_home=hh, platform="cli")
    p.handle_tool_call(
        "hermescube_manage",
        {
            "action": "add",
            "entry_type": "resolve",
            "content": "Use hermescube_manage action=hygiene before world sync; path is $HERMES_HOME/memories/memory.cube",
            "outcome": "success",
        },
    )
    r = json.loads(p.handle_tool_call("hermescube_manage", {"action": "forge", "limit": 5}))
    assert r.get("status") == "forged"
    assert (r.get("stats") or {}).get("forged", 0) >= 1
    drafts = list_drafts(hh)
    assert drafts
    p.shutdown()
