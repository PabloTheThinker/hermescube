"""Day-to-day durability: turns and MEMORY.md mirrors must not be lost."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hermescube.provider import CubeMemoryProvider
from hermescube.cube import CubeFile


def test_sync_turn_persists_before_return():
    """Crash-safe contract: after sync_turn returns, entry is on disk."""
    with tempfile.TemporaryDirectory() as td:
        p = CubeMemoryProvider()
        p.initialize(session_id="d2d", hermes_home=td, platform="cli")
        path = p._cube_path
        p.sync_turn(
            "Remember my favorite color is teal.",
            "Got it — favorite color is teal.",
            session_id="d2d",
        )
        n = p._cube.entry_count
        p.shutdown()
        # reopen fresh
        c = CubeFile.open(path)
        entries = c.read_l1()
        assert len(entries) >= 1
        blob = " ".join(e.description for e in entries)
        assert "teal" in blob.lower()
        c.close()
        assert n >= 1


def test_memory_write_mirror_extension():
    """Built-in MEMORY.md write lands as durable cube extension."""
    with tempfile.TemporaryDirectory() as td:
        p = CubeMemoryProvider()
        p.initialize(session_id="mw", hermes_home=td, platform="cli")
        p.on_memory_write(
            "add",
            "memory",
            "Gateway restart uses sudo -n systemctl restart hermes-gateway",
            metadata={"write_origin": "memory_tool"},
        )
        entries = p._cube.read_l1()
        assert any(
            e.data and e.data.get("extension_of") == "MEMORY.md"
            for e in entries
        )
        assert any("hermes-gateway" in e.description for e in entries)
        # survives reopen
        path = p._cube_path
        p.shutdown()
        c = CubeFile.open(path)
        assert any("hermes-gateway" in e.description for e in c.read_l1())
        c.close()


def test_day_conversation_roundtrip_prefetch():
    """Multi-turn day flow: talk → later session still recalls."""
    with tempfile.TemporaryDirectory() as td:
        p1 = CubeMemoryProvider()
        p1.initialize(session_id="s1", hermes_home=td, platform="cli")
        p1.sync_turn(
            "My deploy host is called Northstar.",
            "Noted: deploy host is Northstar.",
            session_id="s1",
        )
        p1.on_memory_write("add", "user", "User timezone is America/Chicago")
        p1.on_session_end([])
        p1.shutdown()

        p2 = CubeMemoryProvider()
        p2.initialize(session_id="s2", hermes_home=td, platform="cli")
        text = p2.prefetch("what is my deploy host") or ""
        text2 = p2.prefetch("timezone") or ""
        assert "Northstar" in text or "northstar" in text.lower()
        assert "Chicago" in text2 or "chicago" in text2.lower()
        block = p2.system_prompt_block()
        assert "MEMORY.md" in block or "extension" in block.lower()
        p2.shutdown()
