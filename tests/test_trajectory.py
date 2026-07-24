"""Trajectory observe tests."""

from __future__ import annotations

import json
from pathlib import Path

from hermescube import CubeFile
from hermescube.trajectory import (
    extract_trajectories,
    forge_trajectory,
    observe_messages,
    scrub,
)
from hermescube.provider import CubeMemoryProvider


def test_scrub_secrets_and_paths():
    s = scrub("token=abc123 path=/home/ilo/projects/x")
    assert "abc123" not in s
    assert "/home/ilo" not in s
    assert "$HOME" in s or "***" in s


def test_extract_and_forge(tmp_path: Path):
    msgs = [
        {"role": "user", "content": "Ship cube trajectory observe feature"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "terminal", "arguments": '{"command":"pytest"}'}},
                {"function": {"name": "patch", "arguments": '{"path":"x.py"}'}},
                {"function": {"name": "terminal", "arguments": '{"command":"git push"}'}},
            ],
        },
    ]
    trajs = extract_trajectories(msgs, min_tools=3)
    assert len(trajs) >= 1
    assert "terminal" in trajs[0]["tool_names"]

    c = CubeFile.create(str(tmp_path / "t.cube"))
    hh = tmp_path / "h"
    (hh / "memories").mkdir(parents=True)
    st = observe_messages(c, msgs, hermes_home=hh, min_tools=3)
    assert st["forged"] >= 1
    assert st["drafts"]
    assert Path(st["drafts"][0]).is_file()
    body = Path(st["drafts"][0]).read_text()
    assert "terminal" in body and "Draft" in body
    # idempotent
    st2 = observe_messages(c, msgs, hermes_home=hh, min_tools=3)
    assert st2["forged"] == 0
    c.close()


def test_provider_observe_action(tmp_path: Path):
    hh = str(tmp_path / "hh")
    Path(hh, "memories").mkdir(parents=True)
    p = CubeMemoryProvider()
    p.initialize(session_id="o", hermes_home=hh, platform="cli")
    r = json.loads(
        p.handle_tool_call(
            "hermescube_manage",
            {
                "action": "observe",
                "goal": "Run tests and ship cube trajectory",
                "tools": ["terminal", "patch", "terminal", "git"],
            },
        )
    )
    assert r.get("status") == "observed"
    assert (r.get("stats") or {}).get("forged", 0) >= 1
    p.shutdown()


def test_skip_memory_only_chain():
    msgs = [
        {"role": "user", "content": "remember?"},
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "hermescube_search", "arguments": "{}"}},
                {"function": {"name": "memory", "arguments": "{}"}},
                {"function": {"name": "session_search", "arguments": "{}"}},
            ],
        },
    ]
    assert extract_trajectories(msgs, min_tools=3) == []
