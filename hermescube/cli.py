"""CLI — hermescube init, append, query, info, evolve, dump."""

from __future__ import annotations

import argparse
import json
import sys

from hermescube.cube import CubeFile
from hermescube.har import HARQueryEngine
from hermescube import hrr


def cmd_init(args: argparse.Namespace) -> None:
    CubeFile.create(
        args.path,
        dim=args.dim,
        l2_buckets=args.buckets,
    )
    print(f"Created: {args.path}")
    print(f"  dim={args.dim} buckets={args.buckets}")
    if hrr.has_numpy():
        print("  backend: numpy")
    else:
        print("  backend: pure-python")


def cmd_info(args: argparse.Namespace) -> None:
    with CubeFile.open(args.path) as cube:
        info = cube.info()
        print(f"Path: {info['path']}")
        print(f"Entries: {info['entries']}")
        print(f"Dimension: {info['dim']}")
        print(f"L1 data size: {info['l1_data_size']} bytes")
        print(f"L3 β offset: {info['l3_offset']}")
        print(f"L2 buckets: {info['l2_buckets']['count']} total, "
              f"{info['l2_buckets']['non_empty']} non-empty")
        print(f"File size: {info['file_size']} bytes")
        print(f"Backend: {'numpy' if info['has_numpy'] else 'pure-python'}")

        types = cube.count_by_type()
        if types:
            print("\nEntry type breakdown:")
            for t, count in sorted(types.items(), key=lambda x: -x[1]):
                print(f"  {t}: {count}")


def cmd_append(args: argparse.Namespace) -> None:
    with CubeFile.open(args.path) as cube:
        entry = cube.append(
            entry_type=args.type,
            description=args.desc,
            data=json.loads(args.data) if args.data else {},
            causal_parents=args.parents.split(",") if args.parents else [],
            outcome=args.outcome,
        )
        # Update β lightly on append
        engine = HARQueryEngine(cube)
        engine.update_beta_on_append(entry.vector)
        print(f"Appended: {entry.id} [{entry.entry_type}] {entry.description[:60]}")


def cmd_query(args: argparse.Namespace) -> None:
    text = args.text or sys.stdin.read().strip()
    with CubeFile.open(args.path) as cube:
        engine = HARQueryEngine(cube)
        results = engine.query(text, top_k=args.top)

        if not results:
            print("No results.")
            return

        print(f"Query: {text[:60]}")
        print(f"Results (top {len(results)}):")
        for i, (entry, score) in enumerate(results, 1):
            outcome = f" [{entry.outcome}]" if entry.outcome != "none" else ""
            print(f"  {i}. [{entry.entry_type}{outcome}] "
                  f"{entry.description[:120]} score={score:.4f}")


def cmd_evolve(args: argparse.Namespace) -> None:
    with CubeFile.open(args.path) as cube:
        engine = HARQueryEngine(cube)
        stats = engine.evolve()
        print("Evolution complete:")
        for k, v in stats.items():
            print(f"  {k}: {v}")


def cmd_dump(args: argparse.Namespace) -> None:
    with CubeFile.open(args.path) as cube:
        entries = cube.read_l1()
        if args.jsonl:
            for e in entries:
                print(json.dumps(e.as_dict()))
        else:
            print(f"Total entries: {len(entries)}")
            for e in entries:
                outcome = f" outcome={e.outcome}" if e.outcome != "none" else ""
                print(f"  [{e.timestamp[:19]}] {e.id} [{e.entry_type}{outcome}] "
                      f"{e.description[:80]}")


def cmd_beta(args: argparse.Namespace) -> None:
    with CubeFile.open(args.path) as cube:
        beta = cube.read_l3()
        if args.show:
            print(f"β vector ({len(beta)}-dim, norm={hrr.norm(beta):.6f}):")
            print(list(beta))
        else:
            print(f"β norm: {hrr.norm(beta):.6f}")
            print(f"β dim: {len(beta)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hermescube",
        description="Binary columnar archive with holographic associative retrieval",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Create empty .cube file")
    p_init.add_argument("path")
    p_init.add_argument("--dim", type=int, default=256)
    p_init.add_argument("--buckets", type=int, default=64)

    # info
    p_info = sub.add_parser("info", help="Show cube stats")
    p_info.add_argument("path")

    # append
    p_append = sub.add_parser("append", help="Append an entry")
    p_append.add_argument("path")
    p_append.add_argument("--type", "-t", required=True,
                          choices=["enter", "leave", "landmark", "belief",
                                   "trait", "evolution", "focus",
                                   "epoch_transition", "resolve", "relationship"])
    p_append.add_argument("--desc", "-d", required=True)
    p_append.add_argument("--data", help="JSON data")
    p_append.add_argument("--parents", help="Comma-separated parent IDs")
    p_append.add_argument("--outcome", default="none",
                          choices=["none", "success", "failure", "pending", "superseded"])

    # query
    p_query = sub.add_parser("query", help="HAR query")
    p_query.add_argument("path")
    p_query.add_argument("text", nargs="?", default="")
    p_query.add_argument("--top", type=int, default=10)

    # evolve
    p_evolve = sub.add_parser("evolve", help="Run evolution cycle")
    p_evolve.add_argument("path")

    # dump
    p_dump = sub.add_parser("dump", help="List all entries")
    p_dump.add_argument("path")
    p_dump.add_argument("--jsonl", action="store_true", help="JSONL format")

    # beta
    p_beta = sub.add_parser("beta", help="Show β vector stats")
    p_beta.add_argument("path")
    p_beta.add_argument("--show", action="store_true", help="Print full vector")

    args = parser.parse_args(argv)

    commands = {
        "init": cmd_init,
        "info": cmd_info,
        "append": cmd_append,
        "query": cmd_query,
        "evolve": cmd_evolve,
        "dump": cmd_dump,
        "beta": cmd_beta,
    }

    try:
        commands[args.command](args)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.command in ("query", "append", "evolve", "info", "dump", "beta"):
            print("  (is the cube file valid?)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
