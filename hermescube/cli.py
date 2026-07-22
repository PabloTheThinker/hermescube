"""CLI — hermescube init, append, query, info, evolve, dump."""

from __future__ import annotations

import argparse
import json
import os
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


def _default_cube_path() -> str:
    """User Hermes home cube — never the project checkout."""
    import os
    from pathlib import Path

    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return str(Path(home) / "memories" / "memory.cube")


def main(argv: list[str] | None = None) -> int:
    default_path = _default_cube_path()
    parser = argparse.ArgumentParser(
        prog="hermescube",
        description=(
            "Binary columnar archive with holographic associative retrieval. "
            f"Default path: $HERMES_HOME/memories/memory.cube ({default_path})"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_path(p: argparse.ArgumentParser, *, required_create: bool = False) -> None:
        p.add_argument(
            "path",
            nargs="?" if not required_create else None,
            default=None if required_create else default_path,
            help=f"Path to .cube (default: {default_path})",
        )

    # init — still requires path OR defaults to user cube
    p_init = sub.add_parser("init", help="Create empty .cube file")
    p_init.add_argument(
        "path",
        nargs="?",
        default=default_path,
        help=f"Path to create (default: {default_path})",
    )
    p_init.add_argument("--dim", type=int, default=256)
    p_init.add_argument("--buckets", type=int, default=64)

    # info
    p_info = sub.add_parser("info", help="Show cube stats")
    add_path(p_info)

    # append
    p_append = sub.add_parser("append", help="Append an entry")
    add_path(p_append)
    p_append.add_argument("--type", "-t", required=True,
                          choices=["enter", "leave", "landmark", "belief",
                                   "trait", "evolution", "focus",
                                   "epoch_transition", "resolve", "relationship"])
    p_append.add_argument("--desc", "-d", required=True)
    p_append.add_argument("--data", help="JSON data")
    p_append.add_argument("--parents", help="Comma-separated parent IDs")
    p_append.add_argument("--outcome", default="none",
                          choices=["none", "success", "failure", "pending", "superseded"])

    # query — [cube_path] query words…  OR  query words… --cube PATH
    p_query = sub.add_parser("query", help="HAR query")
    p_query.add_argument(
        "args",
        nargs="*",
        help="Optional cube path (.cube) then query text",
    )
    p_query.add_argument(
        "--cube",
        dest="cube_opt",
        default=None,
        help=f"Cube path (default: {default_path})",
    )
    p_query.add_argument("--top", type=int, default=10)

    # evolve
    p_evolve = sub.add_parser("evolve", help="Run evolution cycle")
    add_path(p_evolve)

    # dump
    p_dump = sub.add_parser("dump", help="List all entries")
    add_path(p_dump)
    p_dump.add_argument("--jsonl", action="store_true", help="JSONL format")

    # beta
    p_beta = sub.add_parser("beta", help="Show β vector stats")
    add_path(p_beta)
    p_beta.add_argument("--show", action="store_true", help="Print full vector")

    # doctor — hermes wire check
    p_doc = sub.add_parser("doctor", help="Check Hermes wire + user cube path")
    p_doc.add_argument(
        "--hermes-home",
        default=None,
        help="Override HERMES_HOME",
    )

    # update — pull + reinstall into user Hermes home (like hermes plugins update)
    p_up = sub.add_parser(
        "update",
        help="Update HermesCube install (git pull plugin + pip reinstall; cube data untouched)",
    )
    p_up.add_argument(
        "--hermes-home",
        default=None,
        help="Override HERMES_HOME",
    )
    p_up.add_argument(
        "--check",
        action="store_true",
        help="Only report whether update is available (no install)",
    )

    args = parser.parse_args(argv)

    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "update":
        return cmd_update(args)

    if args.command == "query":
        # Parse [path.cube] query words… compatibility with tests + everyday CLI
        qargs = list(args.args or [])
        path = args.cube_opt or default_path
        if qargs and (
            qargs[0].endswith(".cube")
            or qargs[0].endswith(".CUBE")
            or (os.path.sep in qargs[0] and os.path.exists(qargs[0]))
        ):
            path = qargs[0]
            text = " ".join(qargs[1:])
        else:
            text = " ".join(qargs)
        args.path = path
        args.text = text

    # Ensure parent dir for default user cube on init
    if args.command == "init":
        from pathlib import Path
        Path(args.path).expanduser().parent.mkdir(parents=True, exist_ok=True)

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
            print(f"  path={getattr(args, 'path', '?')}", file=sys.stderr)
            print("  (is the cube file valid? try: hermescube init)", file=sys.stderr)
        return 1


def cmd_doctor(args: argparse.Namespace) -> int:
    import os
    from pathlib import Path

    home = Path(args.hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    cube = home / "memories" / "memory.cube"
    plugin = home / "plugins" / "hermescube"
    cfg = home / "config.yaml"
    print("HermesCube doctor")
    print(f"  HERMES_HOME: {home}")
    print(f"  cube:        {cube}  {'EXISTS' if cube.is_file() else 'missing (ok until first use)'}")
    print(f"  plugin dir:  {plugin}  {'OK' if (plugin / '__init__.py').is_file() else 'MISSING'}")
    print(f"  config:      {cfg}  {'OK' if cfg.is_file() else 'MISSING'}")
    provider = None
    if cfg.is_file():
        try:
            import yaml
            c = yaml.safe_load(cfg.read_text()) or {}
            provider = (c.get("memory") or {}).get("provider")
        except Exception as e:
            print(f"  config parse error: {e}")
    print(f"  memory.provider: {provider or '(unset)'}")
    try:
        import hermescube
        print(f"  package: {hermescube.__version__} @ {hermescube.__file__}")
    except Exception as e:
        print(f"  package: NOT IMPORTABLE ({e})")
        return 1
    if provider != "hermescube":
        print("  hint: hermes config set memory.provider hermescube")
        print("        or: ./scripts/install_hermes.sh")
    print("  update: hermescube update   # or: hermes plugins update hermescube")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Update user install — delegates to scripts/update.sh (git + pip).

    Integrates with Hermes:
      hermes plugins update hermescube   # git pull only
      hermescube update                  # git pull + pip reinstall
    """
    import os
    import shutil
    import subprocess
    from pathlib import Path

    home = Path(
        args.hermes_home
        or os.environ.get("HERMES_HOME")
        or (Path.home() / ".hermes")
    )
    plugin = home / "plugins" / "hermescube"
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)

    if args.check:
        if not (plugin / ".git").is_dir():
            print(f"check: no git plugin at {plugin}")
            print("  install with: hermes plugins install PabloTheThinker/hermescube")
            return 1
        r = subprocess.run(
            ["git", "-C", str(plugin), "fetch", "--quiet"],
            capture_output=True,
            text=True,
            env=env,
        )
        if r.returncode != 0:
            print(f"check: fetch failed: {(r.stderr or r.stdout).strip()}")
            return 1
        local = subprocess.check_output(
            ["git", "-C", str(plugin), "rev-parse", "HEAD"], text=True
        ).strip()
        remote = subprocess.check_output(
            ["git", "-C", str(plugin), "rev-parse", "@{u}"], text=True, stderr=subprocess.DEVNULL
        ).strip() if subprocess.run(
            ["git", "-C", str(plugin), "rev-parse", "@{u}"], capture_output=True
        ).returncode == 0 else ""
        if not remote:
            # try origin/main
            for ref in ("origin/main", "origin/master"):
                rr = subprocess.run(
                    ["git", "-C", str(plugin), "rev-parse", ref],
                    capture_output=True,
                    text=True,
                )
                if rr.returncode == 0:
                    remote = rr.stdout.strip()
                    break
        print(f"local:  {local[:12]}")
        print(f"remote: {(remote or 'unknown')[:12]}")
        if remote and local != remote:
            print("update available → run: hermescube update")
            return 0
        print("already up to date")
        return 0

    # Locate update.sh next to package or under plugin tree
    candidates = [
        plugin / "scripts" / "update.sh",
        Path(__file__).resolve().parent.parent / "scripts" / "update.sh",
    ]
    script = next((p for p in candidates if p.is_file()), None)
    if script is None:
        # Fallback: hermes plugins update only
        print("scripts/update.sh not found — trying: hermes plugins update hermescube")
        hermes = shutil.which("hermes")
        if not hermes:
            print("ERROR: hermes CLI not found and no update.sh", file=sys.stderr)
            return 1
        r = subprocess.run([hermes, "plugins", "update", "hermescube"], env=env)
        return r.returncode

    print(f"→ {script}")
    r = subprocess.run(["bash", str(script)], env=env)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
