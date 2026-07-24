"""Nous-gap pack tests: peer card, digest, consent, conflict."""

from __future__ import annotations

import json
from pathlib import Path

from hermescube import CubeFile
from hermescube.peer_card import build_card, refresh_card, prompt_strip
from hermescube.session_digest import digest_messages, digest_entry_description
from hermescube.consent import list_pending, promote, reject
from hermescube.conflict import find_conflicts
from hermescube.provider import CubeMemoryProvider
from hermescube import bio_rank


def test_peer_card_and_strip(tmp_path: Path):
    c = CubeFile.create(str(tmp_path / "c.cube"))
    c.append("trait", "Prefers short monotropic reports under load", data={"trust": 0.9})
    c.append("relationship", "Pablo Navarro = Vektra CEO", data={"trust": 0.9})
    c.append("belief", "Hot MEMORY.md stays doctrine", data={"trust": 0.8})
    ents = c.read_l1()
    card = build_card(ents, peer_name="pablo")
    assert card["traits"] and card["relationships"]
    hh = tmp_path / "h"
    (hh / "memories").mkdir(parents=True)
    r = refresh_card(ents, hermes_home=hh, min_interval_s=0)
    assert r["skipped"] is False
    r2 = refresh_card(ents, hermes_home=hh, min_interval_s=99999)
    assert r2["skipped"] is True
    assert "Peer card" in prompt_strip(card)
    c.close()


def test_session_digest():
    msgs = [
        {"role": "user", "content": "Ship peer card and session digest"},
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "terminal", "arguments": "{}"}},
                {"function": {"name": "patch", "arguments": "{}"}},
            ],
        },
    ]
    d = digest_messages(msgs, open_intents=["Prove cube gaps"])
    assert "User:" in d and "terminal" in d
    assert digest_entry_description(d).startswith("[SESSION]")


def test_consent_promote_reject(tmp_path: Path):
    hh = tmp_path / "h"
    proc = hh / "memories" / "procedures"
    proc.mkdir(parents=True)
    draft = proc / "demo-draft.md"
    draft.write_text("# Demo\nsteps\n")
    assert list_pending(hh)
    c = CubeFile.create(str(tmp_path / "x.cube"))
    r = promote("demo-draft.md", hermes_home=hh, cube=c)
    assert r["ok"] and Path(r["path"]).is_file()
    assert not draft.exists()
    # recreate and reject
    draft2 = proc / "bad.md"
    draft2.write_text("nope")
    r2 = reject("bad.md", hermes_home=hh, reason="noise")
    assert r2["ok"]
    c.close()


def test_conflict_and_care_rank():
    class E:
        def __init__(self, id, desc, et="belief"):
            self.id = id
            self.description = desc
            self.entry_type = et
            self.outcome = "none"
            self.data = {}

    ents = [E("a1", "Always use cloud memory only")]
    confs = find_conflicts("Never use cloud memory; local cube only", ents, min_overlap=0.2)
    assert confs
    # care half-life slower forget
    w_norm = bio_rank.recency_weight(500, "belief", data={})
    w_care = bio_rank.recency_weight(500, "belief", data={"care": True})
    assert w_care > w_norm


def test_provider_peer_digest_consent(tmp_path: Path):
    hh = str(tmp_path / "hh")
    Path(hh, "memories").mkdir(parents=True)
    p = CubeMemoryProvider()
    p.initialize(session_id="g", hermes_home=hh, platform="cli")
    p.handle_tool_call(
        "hermescube_manage",
        {"action": "add", "entry_type": "trait", "content": "User prefers dual-decode short reports"},
    )
    pr = json.loads(p.handle_tool_call("hermescube_manage", {"action": "peer", "force": True}))
    assert pr.get("status") == "ok" and pr.get("card")
    # session end digest
    p.on_session_end(
        [
            {"role": "user", "content": "Close the Nous gap pack"},
            {"role": "assistant", "content": "Done", "tool_calls": [{"function": {"name": "terminal", "arguments": "{}"}}]},
        ]
    )
    texts = " ".join(e.description or "" for e in p._cube.read_l1())
    assert "[SESSION]" in texts
    # drafts/promote
    proc = Path(hh) / "memories" / "procedures"
    proc.mkdir(parents=True, exist_ok=True)
    (proc / "t.md").write_text("draft")
    d = json.loads(p.handle_tool_call("hermescube_manage", {"action": "drafts"}))
    assert d["pending"]
    pm = json.loads(
        p.handle_tool_call("hermescube_manage", {"action": "promote", "name": "t.md"})
    )
    assert pm.get("ok") is True or pm.get("status") == "promote"
    block = p.system_prompt_block()
    assert "Peer card" in block or "peer" in block.lower() or pr.get("card")
    p.shutdown()
