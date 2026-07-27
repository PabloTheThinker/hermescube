"""Hermes-aligned A− lifts: trust×IR, user_id soft filter, session flush, extract."""

from __future__ import annotations

import time
from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.har import HARQueryEngine
from hermescube.provider import (
    CubeMemoryProvider,
    _MERGED_PRIOR_CONTEXT_HEADER,
    _MERGED_SUMMARY_DELIMITER,
    _user_content_for_extract,
)


def test_trust_ranks_equal_lexical_twins(tmp_path: Path):
    cube = CubeFile.create(str(tmp_path / "t.cube"))
    cube.append(
        "belief",
        "AuthService uses Redis for session storage",
        data={"trust": 0.3, "durable": True, "source": "seed"},
    )
    cube.append(
        "belief",
        "AuthService uses Redis for session storage",
        data={"trust": 0.95, "durable": True, "source": "seed"},
    )
    eng = HARQueryEngine(cube)
    hits = eng.query("AuthService Redis session", top_k=2)
    assert hits
    top = hits[0][0]
    assert float((top.data or {}).get("trust") or 0) >= 0.9
    cube.close()


def test_user_id_soft_boost_never_drops_unlabeled(tmp_path: Path):
    cube = CubeFile.create(str(tmp_path / "u.cube"))
    cube.append(
        "belief",
        "Legacy unlabeled Redis tip for AuthService",
        data={"trust": 0.9, "durable": True},
    )
    cube.append(
        "belief",
        "User-a AuthService Redis preference",
        data={"trust": 0.7, "durable": True, "user_id": "alice"},
    )
    eng = HARQueryEngine(cube)
    eng._active_user_id = "alice"
    hits = eng.query("AuthService Redis", top_k=5)
    descs = [e.description for e, _ in hits]
    assert any("Legacy unlabeled" in d for d in descs)
    assert any("User-a" in d for d in descs)
    cube.close()


def test_session_end_flushes_before_switch(tmp_path: Path):
    hh = tmp_path / "hh"
    (hh / "memories").mkdir(parents=True)
    p = CubeMemoryProvider(auto_extract=False)
    p.initialize(session_id="s1", hermes_home=str(hh))
    for i in range(6):
        p.sync_turn(f"Remember AuthService fact {i}", f"Noted durable {i}")
    # Force queue work to be non-trivial
    done = {"ok": False}
    real_submit = p._sync_queue.submit

    def tracked(fn):
        def wrapped():
            fn()
            done["ok"] = True

        return real_submit(wrapped)

    p._sync_queue.submit = tracked  # type: ignore[method-assign]
    p.on_session_end([])
    assert done["ok"] is True
    p.on_session_switch("s2", parent_session_id="parent-x", reset=True)
    assert p._session_id == "s2"
    assert p._parent_session_id == "parent-x"
    p.shutdown()


def test_user_id_tagged_on_sync_turn(tmp_path: Path):
    hh = tmp_path / "hh"
    (hh / "memories").mkdir(parents=True)
    p = CubeMemoryProvider(auto_extract=False)
    p.initialize(
        session_id="s1",
        hermes_home=str(hh),
        user_id="bob",
        user_id_alt="bob-alt",
    )
    p.sync_turn(
        "I prefer dark mode for the dashboard",
        "Locked. Dark mode is your preference.",
    )
    p._sync_queue.flush(timeout=5.0)
    ents = p._cube.read_l1()
    tagged = [e for e in ents if (e.data or {}).get("user_id") == "bob"]
    assert tagged
    p.shutdown()


def test_pre_delimiter_extract_harvests_user_not_summary():
    real = "I prefer structured logging across AuthService"
    summary = "Summary of conversation: discussed many things about logging"
    merged = (
        f"{_MERGED_PRIOR_CONTEXT_HEADER}\n{real}\n"
        f"{_MERGED_SUMMARY_DELIMITER}\n{summary}"
    )
    out = _user_content_for_extract({"role": "user", "content": merged})
    assert out is not None
    assert "prefer structured logging" in out
    assert "Summary of conversation" not in out

    assert (
        _user_content_for_extract(
            {"role": "user", "content": "Summary: we talked about auth"}
        )
        is None
    )


def test_auto_extract_skips_compaction_summary(tmp_path: Path):
    hh = tmp_path / "hh"
    (hh / "memories").mkdir(parents=True)
    p = CubeMemoryProvider(auto_extract=True)
    p.initialize(session_id="s1", hermes_home=str(hh))
    before = p._cube.entry_count
    p._auto_extract_facts(
        [
            {
                "role": "user",
                "content": "Summary of conversation\nWe decided many things.",
            },
            {
                "role": "user",
                "content": (
                    f"{_MERGED_PRIOR_CONTEXT_HEADER}\n"
                    "I prefer dark mode always\n"
                    f"{_MERGED_SUMMARY_DELIMITER}\n"
                    "Summary: user likes dark mode and many other topics"
                ),
            },
        ]
    )
    ents = p._cube.read_l1()
    extracted = [
        e for e in ents if (e.data or {}).get("source") == "auto_extract"
    ]
    assert extracted
    for e in extracted:
        assert "Summary:" not in (e.description or "")
        assert "Summary of conversation" not in (e.description or "")
    assert p._cube.entry_count >= before
    p.shutdown()
