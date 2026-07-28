"""CubeDream L1 scheduler + L2 circle (dream together)."""

from __future__ import annotations

import json
from pathlib import Path

from hermescube import dream as dream_mod
from hermescube import dream_circle as circle_mod
from hermescube.cli import main
from hermescube.cube import CubeFile
from hermescube.hive import init_hive
from hermescube.manage import known_actions
from hermescube.provider import CubeMemoryProvider


def test_dream_in_known_actions():
    assert "dream" in known_actions()


def test_solo_dream_diary_and_due(tmp_path: Path):
    home = tmp_path / "hh"
    (home / "memories").mkdir(parents=True)
    cube = CubeFile.create(str(home / "memories" / "memory.cube"))
    cube.append("belief", "User prefers dark mode", data={"durable": True})
    cube.close()

    state = dream_mod.read_state(home)
    for _ in range(8):
        state = dream_mod.record_turn(state)
    dream_mod.write_state(home, state)
    st = dream_mod.dream_status(home)
    assert st["due"] is True
    assert any("turn_interval" in r for r in st["reasons"])

    with CubeFile.open(str(home / "memories" / "memory.cube")) as c:
        report = dream_mod.run_solo_dream(c, home, apply=False)
    assert report["ok"]
    assert Path(report["diary"]).is_file()
    st2 = dream_mod.dream_status(home)
    assert st2["due"] is False  # cleared after dream


def test_circle_together_bonus_and_promote(tmp_path: Path):
    hive = tmp_path / "hive"
    init_hive(hive)
    opened = circle_mod.open_circle(hive, opened_by="ilo", topic="billing")
    cid = opened["circle_id"]

    # Same theme from two agents → together
    r1 = circle_mod.post_signal(
        hive,
        cid,
        agent_id="ilo",
        summary="Billing uses Stripe webhooks in eu-west with redis cache",
        entities=["stripe", "redis", "eu-west"],
    )
    r2 = circle_mod.post_signal(
        hive,
        cid,
        agent_id="coder",
        summary="Billing service relies on Stripe webhooks and redis in eu-west",
        entities=["stripe", "redis", "eu-west"],
    )
    assert r1["ok"] and r2["ok"]
    # Entity-heavy keys should collide for chorus
    assert r1["canonical_key"] == r2["canonical_key"]

    scored = circle_mod.score_circle(hive, cid, scorer="ilo")
    assert scored["ok"]
    assert scored["together_count"] >= 1
    top = scored["top"][0]
    assert top["together"] is True
    assert "ilo" in top["supporting_agents"] and "coder" in top["supporting_agents"]
    assert float(top["score_components"]["together"]) == circle_mod.TOGETHER_BONUS

    closed = circle_mod.close_circle(hive, cid, closer="ilo")
    assert closed["ok"]
    assert closed["promoted"] >= 1

    # Draw into agent cube
    home = tmp_path / "agent"
    (home / "memories").mkdir(parents=True)
    with CubeFile.create(str(home / "memories" / "memory.cube")) as cube:
        drawn = circle_mod.draw_circle(hive, cid, cube, agent_id="ilo")
        assert drawn["drawn"] >= 1
        descs = [e.description for e in cube.read_l1()]
        assert any("[CIRCLE:" in d for d in descs)


def test_cli_dream_circle_roundtrip(tmp_path: Path, capsys):
    hive = tmp_path / "hive"
    home = tmp_path / "hh"
    mem = home / "memories"
    mem.mkdir(parents=True)
    c = CubeFile.create(str(mem / "memory.cube"))
    c.append(
        "belief",
        "Deploy pipeline uses github actions and docker registry",
        data={"durable": True, "trust": 0.7},
    )
    c.close()

    assert main(["hive", "init", "--hive", str(hive)]) == 0
    capsys.readouterr()
    rc = main(
        [
            "dream",
            "circle",
            "open",
            "--hive",
            str(hive),
            "--agent",
            "alpha",
            "--topic",
            "deploys",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Opened circle" in out
    cid = out.split("Opened circle ", 1)[1].split()[0]

    # Identical content → same token key (chorus without explicit entities)
    shared = "Deploy pipeline uses github actions and docker registry nightly"
    rc = main(
        [
            "dream",
            "circle",
            "signal",
            "--hive",
            str(hive),
            "--hermes-home",
            str(home),
            "--agent",
            "alpha",
            "--id",
            cid,
            "--content",
            shared,
        ]
    )
    assert rc == 0
    rc = main(
        [
            "dream",
            "circle",
            "signal",
            "--hive",
            str(hive),
            "--agent",
            "beta",
            "--id",
            cid,
            "--content",
            shared,
        ]
    )
    assert rc == 0
    rc = main(
        ["dream", "circle", "score", "--hive", str(hive), "--agent", "alpha", "--id", cid]
    )
    assert rc == 0
    scored_out = capsys.readouterr().out
    assert "together=" in scored_out

    rc = main(
        ["dream", "circle", "close", "--hive", str(hive), "--agent", "alpha", "--id", cid]
    )
    assert rc == 0
    closed = json.loads(capsys.readouterr().out)
    assert closed.get("promoted", 0) >= 1


def test_manage_dream_status(tmp_path: Path):
    home = tmp_path / "hh"
    (home / "memories").mkdir(parents=True)
    CubeFile.create(str(home / "memories" / "memory.cube")).close()
    p = CubeMemoryProvider()
    p.initialize(session_id="t", hermes_home=str(home))
    raw = p.handle_tool_call("hermescube_manage", {"action": "dream", "mode": "status"})
    data = json.loads(raw)
    assert data.get("ok")
    assert data.get("layer") == "L1_soul"
    p.shutdown()
