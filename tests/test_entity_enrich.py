"""Corpus entity mining → persisted landmarks."""

from __future__ import annotations

from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.mirror import enrich_entries_with_mined_entities, extract_entities


def test_expanded_infra_allowlist():
    ents = extract_entities("deploy with helm onto kubernetes behind traefik and datadog")
    low = {e.lower() for e in ents}
    assert "helm" in low
    assert "kubernetes" in low or "k8s" in low or "traefik" in low


def test_enrich_persists_mined_landmarks(tmp_path: Path):
    c = CubeFile.create(str(tmp_path / "m.cube"))
    # Recurring lowercase landmark below allowlist / Cap shapes — needs mining
    for i in range(6):
        c.append(
            "belief",
            f"the billex pipeline batch {i} finished overnight",
            data={"durable": True, "trust": 0.7, "entities": []},
        )
    ents = c.read_l1()
    r = enrich_entries_with_mined_entities(c, ents, max_touch=8)
    assert r["ok"]
    assert r["enriched"] >= 1
    labels = [
        e.description
        for e in c.read_l1()
        if (e.description or "").startswith("[ENTITY]")
    ]
    assert any("billex" in (x or "").lower() for x in labels)
    n_entity = sum(
        1 for e in c.read_l1() if (e.description or "").startswith("[ENTITY]")
    )
    r2 = enrich_entries_with_mined_entities(c, c.read_l1(), max_touch=8)
    n_entity2 = sum(
        1 for e in c.read_l1() if (e.description or "").startswith("[ENTITY]")
    )
    # Idempotent for already-emitted labels (may add at most leftover phrases)
    assert r2["enriched"] <= 1
    assert n_entity2 <= n_entity + 1
    c.close()
