"""Living chambers pulse tests."""

from __future__ import annotations

import json
from pathlib import Path

from hermescube import CubeFile
from hermescube import living
from hermescube.living import (
    build_catalog,
    chamber_pulse,
    connect_dots,
    prompt_strip,
    load_state,
)
from hermescube.provider import CubeMemoryProvider


def test_catalog_and_connect(tmp_path: Path):
    c = CubeFile.create(str(tmp_path / "l.cube"))
    c.append("belief", "HermesCube warehouse keeps MEMORY.md doctrine", data={"trust": 0.9})
    c.append("belief", "HermesCube provider is hermescube on Parallax", data={"trust": 0.9})
    c.append("resolve", "Shipped HermesCube living pulse for agents", outcome="success")
    c.append("trait", "Pablo wants monotropic short reports", data={"trust": 0.8})
    c.append("landmark", "Session work on HermesCube IR and engram")
    ents = c.read_l1()
    cat = build_catalog(ents)
    assert cat["n_entries"] >= 5
    assert cat["by_type"]
    dots = connect_dots(c, ents, max_links=3)
    assert dots["links"] >= 1
    linked = [e for e in c.read_l1() if (e.description or "").startswith("[DOT]")]
    assert linked
    c.close()


def test_chamber_pulse(tmp_path: Path):
    hh = tmp_path / "h"
    (hh / "memories").mkdir(parents=True)
    c = CubeFile.create(str(hh / "memories" / "memory.cube"))
    for i, t in enumerate(
        [
            ("relationship", "Pablo Navarro = Vektra CEO"),
            ("trait", "Prefers dual-decode short reports"),
            ("belief", "Hot MEMORY.md stays doctrine alongside Cube"),
            ("belief", "Cube is deep warehouse with Yield Gradient"),
            ("focus", "Make HermesCube a living archive"),
            ("landmark", "Mission Zero cash-first path"),
        ]
    ):
        c.append(t[0], t[1], data={"trust": 0.8})
    rep = chamber_pulse(c, hermes_home=hh, engram=None, max_connect=3)
    assert rep["ok"] is True
    assert "catalog" in rep["chambers"]
    assert Path(hh / "memories" / "catalog.json").is_file()
    assert Path(hh / "memories" / "living_state.json").is_file()
    st = load_state(hh)
    assert st and st.get("alive")
    strip = prompt_strip(hh)
    assert "Living archive" in strip
    c.close()


def test_provider_pulse(tmp_path: Path):
    hh = str(tmp_path / "hh")
    Path(hh, "memories").mkdir(parents=True)
    p = CubeMemoryProvider()
    p.initialize(session_id="liv", hermes_home=hh, platform="cli")
    for content, et in [
        ("Pablo Navarro = Vektra CEO", "relationship"),
        ("HermesCube never wipes memory.cube", "belief"),
        ("HermesCube update pulls plugin only", "belief"),
        ("Make living chambers work", "focus"),
    ]:
        p.handle_tool_call(
            "hermescube_manage",
            {"action": "add", "entry_type": et, "content": content},
        )
    r = json.loads(p.handle_tool_call("hermescube_manage", {"action": "pulse"}))
    assert r.get("status") == "pulse"
    assert (r.get("report") or {}).get("ok") is True
    assert Path(hh, "memories", "catalog.json").is_file()
    block = p.system_prompt_block()
    assert "Living archive" in block or (r["report"].get("summary"))
    p.shutdown()

def test_prompt_strip_renders_chamber_breakdown(tmp_path):
    """The catalog chamber report stored the histogram under "types" while
    prompt_strip read "by_chamber", so the breakdown line never rendered."""
    hh = tmp_path / "home"
    (hh / "memories").mkdir(parents=True)
    cube = CubeFile.create(str(tmp_path / "m.cube"))
    for et, desc in [
        ("trait", "operator prefers concise technical answers"),
        ("relationship", "pablo owns the memory subsystem roadmap"),
        ("belief", "redis cache reduces auth-service latency"),
        ("resolve", "standardise on structured logging"),
        ("landmark", "shipped the postgres migration"),
        ("focus", "investigating the queue retry storm"),
    ]:
        cube.append(entry_type=et, description=desc, outcome="success")

    report = living.chamber_pulse(cube, hermes_home=str(hh))
    by_chamber = report["chambers"]["catalog"].get("by_chamber")
    assert by_chamber, "catalog chamber must expose by_chamber for prompt_strip"

    strip = living.prompt_strip(str(hh))
    assert "- Chambers:" in strip
    # ordered by descending count, so the breakdown is stable across pulses
    counts = [
        int(part.split(":")[1])
        for part in strip.split("- Chambers: ")[1].split("\n")[0].split(" · ")
    ]
    assert counts == sorted(counts, reverse=True)

    # high_load keeps the strip minimal
    assert "- Chambers:" not in living.prompt_strip(str(hh), high_load=True)


def test_prompt_strip_surfaces_triage_growth_relations(tmp_path: Path):
    hh = tmp_path / "home"
    mem = hh / "memories"
    mem.mkdir(parents=True)
    # Seed triage plan + relations + living state with chambers
    from hermescube.triage import save_plan
    from hermescube.relations import RelationStore

    plan = {
        "ok": True,
        "model": "hermescube-triage-v1",
        "counts": {"working_set": 2, "reconsolidate": 1, "consolidate": 3, "archive": 0},
        "control_plan": {"next_focus": "schedule_consolidation"},
        "should_crystalize": True,
    }
    # living state is what prompt_strip reads
    state = {
        "ok": True,
        "summary": "Living pulse: entries=10",
        "chambers": {
            "catalog": {"by_chamber": {"doctrine": 3}, "entities": {"Redis": 4}},
            "triage": {
                "counts": plan["counts"],
                "next_focus": "schedule_consolidation",
            },
            "growth": {"ready": True, "present": ["durable", "procedure"], "axes": {}},
        },
    }
    (mem / "living_state.json").write_text(json.dumps(state), encoding="utf-8")
    RelationStore(hh).record("Redis", "caches", "AuthService")

    strip = living.prompt_strip(str(hh))
    assert "Triage focus: schedule_consolidation" in strip
    assert "Growth merge ready" in strip
    assert "Redis" in strip and "AuthService" in strip
