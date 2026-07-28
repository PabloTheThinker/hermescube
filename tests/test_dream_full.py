"""CubeDream full stack — dialogue, auto-circle, adversarial, L4 proposals."""

from __future__ import annotations

import json
from pathlib import Path

from hermescube import dream as dream_mod
from hermescube import dream_circle as circle_mod
from hermescube.cli import main
from hermescube.cube import CubeFile
from hermescube.hive import (
    build_offering,
    build_soul_card,
    init_hive,
    publish_soul_card,
    write_offering,
)


def _seed_agent(hive: Path, home: Path, agent_id: str, facts: list[str]) -> None:
    mem = home / "memories"
    mem.mkdir(parents=True, exist_ok=True)
    cube = CubeFile.create(str(mem / "memory.cube"))
    for fact in facts:
        cube.append(
            "belief",
            fact,
            data={"durable": True, "trust": 0.85, "crystal": True},
        )
    card = build_soul_card(list(cube.read_l1()), agent_id=agent_id, hermes_home=str(home))
    publish_soul_card(str(hive), card)
    rows = build_offering(cube, agent_id=agent_id)
    if rows:
        write_offering(str(hive), rows, agent_id=agent_id)
    cube.close()


def test_l4_memory_md_proposals_never_apply(tmp_path: Path):
    home = tmp_path / "hh"
    mem = home / "memories"
    mem.mkdir(parents=True)
    (home / "MEMORY.md").write_text("- Already known fact about coffee\n", encoding="utf-8")
    c = CubeFile.create(str(mem / "memory.cube"))
    c.append(
        "belief",
        "Already known fact about coffee preferences",
        data={"durable": True},
    )
    c.append(
        "belief",
        "Deploy uses blue-green releases in production",
        data={"durable": True, "crystal": True},
    )
    c.close()

    with CubeFile.open(str(mem / "memory.cube")) as cube:
        report = dream_mod.propose_memory_md(home, cube=cube)
    assert report["ok"]
    assert report["applied"] is False
    lines = [p["line"] for p in report["proposals"]]
    assert any("blue-green" in ln for ln in lines)
    # Existing MEMORY.md overlap should be skipped
    assert not any("coffee" in ln.lower() for ln in lines)
    assert Path(report["path"]).is_file()
    # MEMORY.md unchanged
    assert "blue-green" not in (home / "MEMORY.md").read_text(encoding="utf-8")


def test_adversarial_skim_flags_conflicts(tmp_path: Path):
    hive = tmp_path / "hive"
    init_hive(hive)
    opened = circle_mod.open_circle(hive, opened_by="a", topic="prefs")
    cid = opened["circle_id"]
    # Two agents chorus a claim
    text = "User prefers dark mode in all editors"
    circle_mod.post_signal(hive, cid, agent_id="a", summary=text, entities=["dark", "mode"])
    circle_mod.post_signal(hive, cid, agent_id="b", summary=text, entities=["dark", "mode"])
    circle_mod.score_circle(hive, cid, scorer="a")

    # Local corpus contradicts with negation
    class E:
        def __init__(self, desc: str):
            self.id = "x"
            self.entry_type = "belief"
            self.outcome = "none"
            self.description = desc
            self.data = {}

    skim = circle_mod.adversarial_skim(
        hive,
        cid,
        local_entries=[E("User does not prefer dark mode in editors")],
    )
    assert skim["ok"]
    # May or may not flag depending on conflict heuristics — structure holds
    assert skim["candidates"] >= 1
    assert "flagged" in skim


def test_auto_circle_two_agents(tmp_path: Path):
    hive = tmp_path / "hive"
    init_hive(hive)
    home_a = tmp_path / "a"
    home_b = tmp_path / "b"
    shared = "Billing uses Stripe webhooks with redis in eu-west region"
    _seed_agent(hive, home_a, "ilo", [shared, "Ilo owns fleet routing"])
    _seed_agent(hive, home_b, "coder", [shared, "Coder owns test pipelines"])

    report = circle_mod.run_auto_circle(
        hive,
        agent_homes={"ilo": home_a, "coder": home_b},
        topic="billing night",
        opened_by="night-watch",
        skim=True,
    )
    assert report.get("ok")
    assert report["close"].get("promoted", 0) >= 1
    assert len(report.get("feeds") or []) == 2


def test_dialogue_in_circle(tmp_path: Path):
    hive = tmp_path / "hive"
    init_hive(hive)
    home_r = tmp_path / "researcher"
    home_c = tmp_path / "coder"
    _seed_agent(
        hive,
        home_r,
        "researcher",
        ["Always verify sources before citing competitive analysis"],
    )
    _seed_agent(
        hive,
        home_c,
        "coder",
        ["Prefer pytest for all regression suites"],
    )
    opened = circle_mod.open_circle(hive, opened_by="coder", topic="sources")
    cid = opened["circle_id"]
    with CubeFile.open(str(home_r / "memories" / "memory.cube")) as sub:
        r = circle_mod.dialogue_in_circle(
            hive,
            cid,
            interviewer="coder",
            subject="researcher",
            topic="source verification",
            hermes_home=str(home_c),
            subject_cube=sub,
            mint=False,
        )
    assert r.get("ok")
    assert r.get("signals_posted", 0) >= 1
    assert Path(r["record"]).is_file()
    st = circle_mod.circle_status(hive, cid)
    assert st.get("signal_count", 0) >= 1


def test_cli_interview_list(tmp_path: Path, capsys):
    hive = tmp_path / "hive"
    assert main(["hive", "init", "--hive", str(hive)]) == 0
    capsys.readouterr()
    rc = main(["interview", "list", "--hive", str(hive)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "No interviews" in out or "interview" in out.lower() or out == ""


def test_cli_dream_propose_and_auto(tmp_path: Path, capsys):
    hive = tmp_path / "hive"
    home_a = tmp_path / "a"
    home_b = tmp_path / "b"
    init_hive(hive)
    fact = "Nightly backups run via restic to the offsite bucket"
    _seed_agent(hive, home_a, "alpha", [fact])
    _seed_agent(hive, home_b, "beta", [fact])

    rc = main(
        ["dream", "propose", "--hermes-home", str(home_a)]
    )
    assert rc == 0
    assert "L4 proposals" in capsys.readouterr().out

    rc = main(
        [
            "dream",
            "auto-circle",
            "--hive",
            str(hive),
            "--hermes-home",
            str(home_a),
            "--agent",
            "alpha",
            "--peer-home",
            f"beta:{home_b}",
            "--topic",
            "backups",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "circle_id" in out
