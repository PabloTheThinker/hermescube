"""CubeVoid — operating core of HermesCube memory (infinite void housing).

Wires HAR + bio_rank + mirror + colony + lexindex into one recall/imprint API
used by the Hermes provider adapter. This is the “system inside the cube.”
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from hermescube import bio_rank
from hermescube import colony as colony_mod
from hermescube import mirror as mirror_mod
from hermescube.colony import ColonyGraph
from hermescube.cube import CubeEntry, CubeFile
from hermescube.framework.lexindex import LexIndex
from hermescube.framework.paths import CubePaths
from hermescube.har import HARQueryEngine

logger = logging.getLogger(__name__)


class CubeVoid:
    """In-cube operating system: recall, imprint trails, board pulse."""

    def __init__(
        self,
        cube: CubeFile,
        engine: HARQueryEngine,
        paths: CubePaths,
        colony: ColonyGraph | None = None,
    ) -> None:
        self.cube = cube
        self.engine = engine
        self.paths = paths
        self.colony = colony
        self.lex = LexIndex()
        self._lex_built_for = -1
        if colony is not None:
            setattr(engine, "_colony", colony)

    def rebuild_lex(self) -> None:
        entries = self.cube.read_l1() or []
        self.lex.build(entries)
        self._lex_built_for = len(entries)

    def _ensure_lex(self) -> None:
        # engine owns resident lex cache via refresh_cache; void lex optional
        n = int(getattr(self.cube, "entry_count", 0) or 0)
        if self._lex_built_for < 0 or (n > 0 and self.lex.entry_count == 0):
            self.rebuild_lex()
            self._lex_built_for = n

    def recall(
        self,
        query: str,
        *,
        top_k: int = 5,
        beta=None,
        centroids=None,
    ) -> list[tuple[CubeEntry, float]]:
        """Full void recall: engine query (mirror+colony inside HAR)."""
        if not query or not query.strip():
            return []
        # Prefer engine hyper path (resident cache)
        results = self.engine.query(
            query,
            top_k=max(top_k, 5),
            beta=beta,
            centroids=centroids,
        )
        # Trail maintenance
        if self.colony is not None and results:
            try:
                # light trail only — no disk save on hot path
                for entry, _ in results[:3]:
                    ents = (entry.data or {}).get("entities") if entry.data else None
                    if ents and len(ents) >= 2:
                        self.colony.deposit(list(ents)[:6], amount=0.12)
                self.colony.mark_dirty()
                # board at most every N recalls / interval
                self.colony.maybe_write_markdown_board(
                    self.paths.colony_board, min_interval_s=300.0, every_n_recalls=20
                )
            except Exception as e:
                logger.debug("void colony pulse: %s", e)
        return results[:top_k]

    def format_prefetch(self, results: list[tuple[CubeEntry, float]]) -> str:
        if not results:
            return ""
        lines = ["[Relevant memories from past sessions:]"]
        for entry, _score in results[:5]:
            ts = entry.timestamp[:10] if entry.timestamp else "unknown"
            layer = bio_rank.cortical_layer(entry.entry_type or "")
            kind = colony_mod.resource_kind(entry.entry_type or "", entry.description or "")
            lines.append(
                f"- [{ts}] [{entry.entry_type}|{layer}|{kind}] {entry.description}"
            )
            if entry.data:
                for k, v in entry.data.items():
                    if k in ("confidence", "source", "trust", "entities"):
                        lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def reinforce(self, entry: CubeEntry, *, amount: float = 0.5) -> None:
        if self.colony is None:
            return
        ents = (entry.data or {}).get("entities") if entry.data else None
        if not ents:
            ents = mirror_mod.extract_entities(entry.description or "")
        if ents:
            self.colony.deposit(list(ents), amount=amount)
            self.colony.register_dance(entry)
            self.colony.save()
            self.colony.mark_dirty()
            self.colony.maybe_write_markdown_board(
                self.paths.colony_board, force=True
            )

    def flush_board(self) -> None:
        if self.colony is not None:
            self.colony.maybe_write_markdown_board(
                self.paths.colony_board, force=True
            )
