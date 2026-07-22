"""CLI integration for 'hermes memory hermescube' commands.

Provides setup, status, and maintenance commands for the
HermesCube memory provider.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def register_cli(subparser) -> None:
    """Register CLI subcommands under 'hermes memory hermescube'.

    Called by hermes_cli.memory_setup when hermescube is the active provider.
    """

    # --- hermescube status ---
    p_status = subparser.add_parser(
        "hermescube-status",
        help="Show HermesCube memory status",
    )

    # --- hermescube evolve ---
    p_evolve = subparser.add_parser(
        "hermescube-evolve",
        help="Run HermesCube evolution cycle (recluster + dedup)",
    )

    # --- hermescube dump ---
    p_dump = subparser.add_parser(
        "hermescube-dump",
        help="Export HermesCube memory entries",
    )
    p_dump.add_argument(
        "--jsonl", action="store_true",
        help="Export as JSONL",
    )
    p_dump.add_argument(
        "--limit", type=int, default=0,
        help="Max entries to show (0 = all)",
    )

    # --- hermescube compact ---
    p_compact = subparser.add_parser(
        "hermescube-compact",
        help="Force-consolidate HermesCube memory (evolve + dedup + embedder save)",
    )


def hermescube_status(args, hermes_home: str) -> int:
    """Show HermesCube memory status."""
    try:
        from hermescube.provider import CubeMemoryProvider

        provider = CubeMemoryProvider()
        provider.initialize(session_id="_cli_status", hermes_home=hermes_home)

        cube_path = provider._cube_path
        if not cube_path or not os.path.isfile(cube_path):
            print("HermesCube: No cube file found — run 'hermes memory setup' to initialize.")
            return 0

        info = provider._cube.info()
        print(f"HermesCube Memory Status")
        print(f"  Path:       {info['path']}")
        print(f"  Entries:    {info['entries']}")
        print(f"  Dimension:  {info['dim']}")
        print(f"  File size:  {info['file_size']} bytes")
        print(f"  Backend:    {'numpy' if info['has_numpy'] else 'pure-python'}")

        type_counts = provider._cube.count_by_type()
        if type_counts:
            print(f"\n  Entry types:")
            for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
                print(f"    {t}: {c}")

        provider.shutdown()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def hermescube_evolve(args, hermes_home: str) -> int:
    """Run evolve cycle on HermesCube."""
    try:
        from hermescube.provider import CubeMemoryProvider

        provider = CubeMemoryProvider()
        provider.initialize(session_id="_cli_evolve", hermes_home=hermes_home)

        print("Running HermesCube evolution...")
        stats = provider.evolve_consolidated()
        print(json.dumps(stats, indent=2))

        provider.shutdown()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def hermescube_dump(args, hermes_home: str) -> int:
    """Dump HermesCube entries."""
    try:
        from hermescube.provider import CubeMemoryProvider

        provider = CubeMemoryProvider()
        provider.initialize(session_id="_cli_dump", hermes_home=hermes_home)

        entries = provider._cube.read_l1()
        if args.limit > 0:
            entries = entries[-args.limit:]

        if args.jsonl:
            for e in entries:
                print(json.dumps(e.as_dict()))
        else:
            print(f"Total entries: {len(entries)}")
            for e in entries:
                outcome = f" outcome={e.outcome}" if e.outcome != "none" else ""
                print(f"  [{e.timestamp[:19]}] {e.id} "
                      f"[{e.entry_type}{outcome}] {e.description[:80]}")

        provider.shutdown()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def hermescube_compact(args, hermes_home: str) -> int:
    """Force-consolidate HermesCube memory."""
    try:
        from hermescube.provider import CubeMemoryProvider

        provider = CubeMemoryProvider()
        provider.initialize(session_id="_cli_compact", hermes_home=hermes_home)

        print("Compacting HermesCube memory...")
        print("  Step 1/3: Evolve (k-means + beta update)")
        stats = provider.evolve_consolidated()
        print(f"    Clusters: {stats.get('clusters', 'N/A')}")
        print(f"    Deduped:  {stats.get('deduped', 0)}")
        print(f"    Quality:  {stats.get('quality_score', 'N/A')}")

        print("  Step 2/3: Refresh snapshot")
        provider._refresh_snapshot()

        print("  Step 3/3: Save embedder")
        if provider._evolve_lambda_trained:
            print("    Embedder saved to disk")
        else:
            print("    Need more entries to train embedder")

        info = provider._cube.info()
        print(f"\n  Cube: {info['entries']} entries, {info['file_size']} bytes")

        provider.shutdown()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
