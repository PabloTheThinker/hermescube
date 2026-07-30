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
        # Living genealogy (soul-age of this cube)
        try:
            from pathlib import Path

            from hermescube.genealogy import growth_status

            home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
            # Infer hermes_home from cube path when under memories/
            cpath = Path(info["path"]).resolve()
            if cpath.parent.name == "memories":
                home = str(cpath.parent.parent)
            g = growth_status(home, cube=cube)
            age = g.get("age") or {}
            print(f"\nLiving version: v{g.get('version')}")
            print(f"  age:        {age.get('label', '—')}  (digital cycles + lived time)")
            print(
                f"  era:        {g.get('era_label') or g.get('era')}  · "
                f"capability {g.get('capability', g.get('strength'))}/100"
            )
            print(f"  diary:      {g.get('cube_md')}")
        except Exception as e:
            print(f"\nLiving version: n/a ({e})")
        try:
            from hermescube.triage import load_plan
            from hermescube.relations import RelationStore

            plan = load_plan(home)
            if plan:
                cp = plan.get("control_plan") or {}
                print(
                    f"\nTriage: focus={cp.get('next_focus')} "
                    f"counts={plan.get('counts')}"
                )
            rel = RelationStore(home).stats()
            print(
                f"Relations: {rel.get('relations')} open "
                f"(path={rel.get('path')})"
            )
            merges = [
                e
                for e in (cube.read_l1() or [])
                if (getattr(e, "data", None) or {}).get("growth_merge")
            ]
            if merges:
                print(f"Growth merge: last={merges[-1].id}")
        except Exception as e:
            print(f"\nCompounding: n/a ({e})")
        try:
            dens = cube.density_stats()
            print("\nDensity (archive packing):")
            print(f"  bytes/entry: {dens['bytes_per_entry']:.0f}")
            print(f"  text+data share: {dens['text_plus_data_share']*100:.1f}%")
            print(f"  vec estimate: {dens['vec_bytes_estimate']} bytes "
                  f"({dens['note']})")
        except Exception as e:
            print(f"\nDensity: n/a ({e})")

        types = cube.count_by_type()
        if types:
            print("\nEntry type breakdown:")
            for t, count in sorted(types.items(), key=lambda x: -x[1]):
                print(f"  {t}: {count}")
        try:
            integ = cube.integrity_check()
            print("\nIntegrity:")
            print(f"  ok: {integ.get('ok')}")
            print(f"  entries_read: {integ.get('entries_read')} "
                  f"(count={integ.get('entry_count')})")
            print(f"  empty_descriptions: {integ.get('empty_descriptions')}")
            print(f"  duplicate_ids: {integ.get('duplicate_ids')}")
            print(f"  bad_vectors: {integ.get('bad_vectors')}")
            print(f"  cube_bytes: {integ.get('cube_bytes')} "
                  f"cubelog_bytes: {integ.get('cubelog_bytes')}")
            for issue in integ.get("issues") or []:
                print(f"  ! {issue}")
        except Exception as e:
            print(f"\nIntegrity: n/a ({e})")


def cmd_growth(args: argparse.Namespace) -> int:
    """Show / refine the living cube genealogy."""
    from pathlib import Path

    from hermescube import genealogy as gen

    home = args.hermes_home or os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    cube = None
    cube_path = Path(home) / "memories" / "memory.cube"
    if cube_path.is_file():
        try:
            cube = CubeFile.open(str(cube_path))
        except Exception:
            cube = None
    try:
        cmd = args.growth_command
        if cmd == "status":
            s = gen.growth_status(home, cube=cube)
            age = s.get("age") or {}
            print(f"Living Cube v{s.get('version')}  — {s.get('era_label') or s.get('era')}")
            print(f"  age:         {age.get('label', '—')}")
            print(f"  capability:  {s.get('capability', s.get('strength'))}/100  (coherence, not age)")
            print(f"  diary:       {s.get('cube_md')}")
            counts = s.get("counts") or {}
            print(f"  durable={counts.get('durable', 0)}  "
                  f"crystals={counts.get('crystals', 0)}  "
                  f"procedures={counts.get('procedures', 0)}  "
                  f"skills={counts.get('skills_installed', 0)}  "
                  f"draws={counts.get('hive_draws', 0)}")
            skills = s.get("skills") or {}
            if skills:
                print("  skills evolving:")
                for name, meta in list(skills.items())[:12]:
                    print(f"    · {name} v{meta.get('version')} "
                          f"(refined {meta.get('refined', 0)}×)")
            return 0
        if cmd == "epochs":
            for e in gen.list_epochs(home, limit=int(args.limit or 30)):
                if e.get("kind") in ("eden", "genesis"):
                    print(f"[C0 Cube of Eden] → {e.get('to')}: {e.get('reason')}")
                else:
                    cyc = e.get("cycle")
                    cyc_s = f"C{cyc} " if cyc is not None else ""
                    print(
                        f"[{cyc_s}{e.get('bump')}] {e.get('from')} → {e.get('to')}  "
                        f"{e.get('reason', '')[:100]}"
                    )
            return 0
        if cmd == "refine":
            if not args.skill or not args.lesson:
                print("Error: --skill and --lesson required", file=sys.stderr)
                return 1
            r = gen.refine_skill(home, args.skill, lesson=args.lesson, cube=cube)
            if not r.get("ok"):
                print(f"Error: {r.get('error')}", file=sys.stderr)
                return 1
            print(
                f"Skill refined: {r.get('skill')} "
                f"{r.get('from_version')} → {r.get('to_version')}"
            )
            g = (r.get("growth") or {})
            if g.get("bumped"):
                age = g.get("age") or {}
                print(f"  cube: v{g.get('from')} → v{g.get('to')}  "
                      f"({age.get('label', '')})")
            return 0
        if cmd == "curate":
            from hermescube.curator import run_curator

            lessons = [args.lesson] if args.lesson else []
            r = run_curator(
                home,
                cube=cube,
                lessons=lessons,
                era_milestone=bool(getattr(args, "milestone", False)),
            )
            refines = r.get("refines") or []
            if refines:
                for rf in refines:
                    print(
                        f"Refined: {rf.get('skill')} "
                        f"{rf.get('from_version')} → {rf.get('to_version')}"
                    )
            else:
                print("Curator: no skill overlaps found for lessons.")
            if r.get("forge"):
                print(f"  forge: {r.get('forge')}")
            if r.get("garden"):
                print(f"  garden: {r.get('garden')}")
            return 0
        print(f"Error: unknown growth command {cmd}", file=sys.stderr)
        return 1
    finally:
        if cube is not None:
            try:
                cube.close()
            except Exception:
                pass


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
            "HermesCube — the library under Hermes. "
            "Each HERMES_HOME owns its own book at memories/memory.cube. "
            f"Default: {default_path}"
        ),
        epilog=(
            "Day one:  hermescube setup | connect | status | query \"…\" | "
            "blackbox prove --claim \"tests pass\" --latest | checkpoint create --name first"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_setup = sub.add_parser(
        "setup",
        help="Install/wire HermesCube for this HERMES_HOME (any Hermes agent user)",
    )
    p_setup.add_argument("--hermes-home", default=None, help="Override HERMES_HOME")
    p_setup.add_argument(
        "--no-install-script",
        action="store_true",
        help="Skip scripts/install_hermes.sh (only connect)",
    )

    p_conn = sub.add_parser(
        "connect",
        help="Attach this HERMES_HOME to its own cube (provider + book + plugin link)",
    )
    p_conn.add_argument("--hermes-home", default=None, help="Override HERMES_HOME")
    p_conn.add_argument("--no-plugin", action="store_true", help="Do not ensure plugin dir")

    p_stat = sub.add_parser(
        "status",
        help="Human library status for this HERMES_HOME (terminal-friendly)",
    )
    p_stat.add_argument("--hermes-home", default=None, help="Override HERMES_HOME")
    p_stat.add_argument("--json", action="store_true", help="JSON output")

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
    p_doc.add_argument(
        "--identity",
        default="",
        help="Agent identity for nested profile sidecars",
    )
    p_doc.add_argument(
        "--workspace",
        default="",
        help="Agent workspace for nested profile sidecars",
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

    # hive — shared collective nexus for multiple Hermes agents
    p_hive = sub.add_parser(
        "hive",
        help="Hive nexus: init/status/pilgrimage/assimilate (multi-agent collective)",
    )
    p_hive.add_argument(
        "hive_command",
        choices=["init", "status", "pilgrimage", "assimilate", "souls"],
        help="Hive operation",
    )
    p_hive.add_argument(
        "--hive",
        default=None,
        help="Hive directory (default: $HERMESCUBE_HIVE)",
    )
    p_hive.add_argument(
        "--hermes-home",
        default=None,
        help="Agent HERMES_HOME (for pilgrimage; default: $HERMES_HOME)",
    )
    p_hive.add_argument(
        "--agent",
        default=None,
        help="Agent id for pilgrimage (default: $HERMES_PROFILE or 'hermes')",
    )
    p_hive.add_argument(
        "--focus",
        default="",
        help="Focus query when drawing collective wisdom",
    )
    p_hive.add_argument(
        "--interview",
        action="store_true",
        help="After upload/draw, interview peer souls (interview-me) and mint skill drafts",
    )
    p_hive.add_argument(
        "--interview-peers",
        type=int,
        default=1,
        help="How many peer souls to interview during pilgrimage (default 1)",
    )

    # interview — peer dialogue at the hive (interview-me protocol)
    p_iv = sub.add_parser(
        "interview",
        help="Peer interview: dialogue/list (agents interview each other at the hive)",
    )
    p_iv.add_argument(
        "interview_command",
        choices=["dialogue", "list"],
        help="Interview operation",
    )
    p_iv.add_argument("--hive", default=None, help="Hive directory (default: $HERMESCUBE_HIVE)")
    p_iv.add_argument("--interviewer", default=None, help="Interviewing agent id")
    p_iv.add_argument("--subject", default=None, help="Subject agent id to interview")
    p_iv.add_argument("--topic", default="shared craft", help="Interview topic")
    p_iv.add_argument(
        "--mode",
        default="discover",
        choices=["clarify", "discover", "brief", "decision", "retrospective", "profile"],
    )
    p_iv.add_argument(
        "--hermes-home",
        default=None,
        help="Where to mint skill drafts (default: $HERMES_HOME)",
    )
    p_iv.add_argument(
        "--no-mint",
        action="store_true",
        help="Do not mint a procedure draft from the brief",
    )
    p_iv.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not offer distilled facts back to the hive",
    )

    # hq — fleet command layer (charters, routing, verification, baseline)
    p_hq = sub.add_parser(
        "hq",
        help="Fleet HQ: charter/list/route/verify/freeze/drift/handoffs",
    )
    p_hq.add_argument(
        "hq_command",
        choices=[
            "charter", "retire", "list", "route", "verify",
            "freeze", "drift", "handoffs", "complete",
        ],
        help="HQ operation",
    )
    p_hq.add_argument("--id", default="", help="For complete: handoff id to settle")
    p_hq.add_argument("--hive", default=None, help="Hive/HQ directory (default: $HERMESCUBE_HIVE)")
    p_hq.add_argument("--agent", default=None, help="Agent id (for charter/retire)")
    p_hq.add_argument("--role", default="specialist", choices=["command", "specialist"])
    p_hq.add_argument("--lane", default="", help="For charter: the durable lane this agent owns")
    p_hq.add_argument("--keywords", default="", help="For charter: comma-separated lane keywords")
    p_hq.add_argument("--boundaries", default="", help="For charter: semicolon-separated boundaries")
    p_hq.add_argument("--task", default="", help="For route: task text to route")

    # harness — grounded self-evolution (witness / critic / verifier / gardener)
    p_growth = sub.add_parser(
        "growth",
        help="Living cube genealogy: status/epochs/refine (starts at 0.0.0)",
    )
    p_growth.add_argument(
        "growth_command",
        choices=["status", "epochs", "refine", "curate"],
        help="Growth operation",
    )
    p_growth.add_argument(
        "--hermes-home",
        default="",
        help="Hermes home (default: $HERMES_HOME or ~/.hermes)",
    )
    p_growth.add_argument("--limit", type=int, default=30, help="For epochs: how many")
    p_growth.add_argument("--skill", default="", help="For refine: skill name")
    p_growth.add_argument(
        "--lesson", default="", help="For refine/curate: lesson text"
    )
    p_growth.add_argument(
        "--milestone",
        action="store_true",
        help="For curate: force era-milestone forge+garden pass",
    )

    p_dream = sub.add_parser(
        "dream",
        help="CubeDream: soul solo dream + hive circle (dream together)",
    )
    p_dream.add_argument(
        "dream_command",
        choices=[
            "status",
            "solo",
            "circle",
            "propose",
            "auto-circle",
        ],
        help="status · solo · propose · auto-circle · circle …",
    )
    p_dream.add_argument(
        "circle_command",
        nargs="?",
        default=None,
        choices=[
            "open",
            "join",
            "signal",
            "score",
            "close",
            "draw",
            "list",
            "status",
            "dialogue",
            "skim",
        ],
        help="For circle: open|join|signal|dialogue|skim|score|close|draw|list|status",
    )
    p_dream.add_argument("--hive", default=None, help="Hive root (default: $HERMESCUBE_HIVE)")
    p_dream.add_argument(
        "--hermes-home",
        default=None,
        help="Agent HERMES_HOME (default: $HERMES_HOME)",
    )
    p_dream.add_argument("--agent", default=None, help="Agent id")
    p_dream.add_argument("--id", default="", help="Circle id")
    p_dream.add_argument("--topic", default="", help="Circle topic")
    p_dream.add_argument(
        "--content",
        default="",
        help="For circle signal: summary text (else distill from cube)",
    )
    p_dream.add_argument(
        "--apply",
        action="store_true",
        help="For solo: run sleep_replay + crystalize (warehouse only)",
    )
    p_dream.add_argument(
        "--commit-crystalize",
        action="store_true",
        help="For solo --apply: crystalize for real (default dry_run)",
    )
    p_dream.add_argument(
        "--subject",
        default="",
        help="For circle dialogue: subject agent id",
    )
    p_dream.add_argument(
        "--peer-home",
        action="append",
        default=[],
        help="For auto-circle: agent_id:/path/to/hermes_home (repeatable)",
    )
    p_dream.add_argument(
        "--interview-pair",
        default="",
        help="For auto-circle: interviewer:subject",
    )
    p_dream.add_argument(
        "--no-skim",
        action="store_true",
        help="For auto-circle: skip adversarial skim",
    )

    p_dense = sub.add_parser(
        "dense",
        help="Portable dense text archive (gzip JSONL) — backup/ship without vectors",
    )
    p_dense.add_argument(
        "dense_command",
        choices=["export", "import", "stats"],
        help="export live→dense · import dense→live · stats on live cube",
    )
    p_dense.add_argument(
        "--cube",
        default=None,
        help="Live .cube path (default: $HERMES_HOME/memories/memory.cube)",
    )
    p_dense.add_argument(
        "--out",
        default=None,
        help="Dense archive path (default: memories/memory.dense.jsonl.gz)",
    )
    p_dense.add_argument(
        "--hermes-home",
        default=None,
        help="Override HERMES_HOME for default paths",
    )

    p_har = sub.add_parser(
        "harness",
        help="Self-evolution harness: status/witness/critic/verify/gardener",
    )
    p_har.add_argument(
        "harness_command",
        choices=["status", "witness", "critic", "verify", "gardener"],
        help="Harness operation",
    )
    p_har.add_argument(
        "--hermes-home",
        default=None,
        help="Agent HERMES_HOME (default: $HERMES_HOME)",
    )
    p_har.add_argument(
        "--desc",
        default="",
        help="For witness: describe the real friction",
    )
    p_har.add_argument(
        "--severity",
        default="medium",
        choices=["low", "medium", "high"],
        help="For witness: friction severity",
    )

    p_bb = sub.add_parser(
        "blackbox",
        help="Flight recorder core: capture / prove / verify (center blackbox organ)",
    )
    p_bb.add_argument(
        "bb_command",
        choices=["capture", "prove", "verify", "status", "breathe"],
        help="capture · prove · verify · status · breathe (full pulmonary cycle)",
    )
    p_bb.add_argument("--session", default=None, help="Session id or prefix")
    p_bb.add_argument("--latest", action="store_true", help="Latest session (default for capture)")
    p_bb.add_argument("--claim", default="", help="For prove: natural language claim")
    p_bb.add_argument("--record", default=None, help="Flight record JSON path")
    p_bb.add_argument("--out", default=None, help="Write capture/prove output path")
    p_bb.add_argument("--hermes-home", default=None, help="Override HERMES_HOME")
    p_bb.add_argument("--no-redact", action="store_true", help="Disable redaction (local debug only)")

    p_ck = sub.add_parser(
        "checkpoint",
        help="Safe-lock identity ark: snapshot cube book + core identity (SOUL/MEMORY/USER)",
    )
    p_ck.add_argument(
        "ck_command",
        choices=["create", "list", "restore"],
        help="create · list · restore",
    )
    p_ck.add_argument("--name", default=None, help="Checkpoint slug / name")
    p_ck.add_argument("--label", default="", help="Human label for this arc mark")
    p_ck.add_argument("--hermes-home", default=None, help="Override HERMES_HOME")
    p_ck.add_argument("--dense", action="store_true", help="Also export dense text archive into checkpoint")
    p_ck.add_argument("--no-tar", action="store_true", help="Skip .tar.gz pack")
    p_ck.add_argument("--with-config", action="store_true", help="On restore: also restore config.yaml")
    p_ck.add_argument("--dry-run", action="store_true", help="Restore: show plan only")
    p_ck.add_argument("--identity-only", action="store_true", help="Restore: SOUL/MEMORY/USER only")
    p_ck.add_argument("--cube-only", action="store_true", help="Restore: cube book only")

    args = parser.parse_args(argv)

    if args.command == "setup":
        return cmd_setup(args)
    if args.command == "connect":
        return cmd_connect(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "update":
        return cmd_update(args)
    if args.command == "hive":
        return cmd_hive(args)
    if args.command == "harness":
        return cmd_harness(args)
    if args.command == "blackbox":
        return cmd_blackbox(args)
    if args.command == "checkpoint":
        return cmd_checkpoint(args)
    if args.command == "hq":
        return cmd_hq(args)
    if args.command == "interview":
        return cmd_interview(args)
    if args.command == "growth":
        return cmd_growth(args)
    if args.command == "dense":
        return cmd_dense(args)
    if args.command == "dream":
        return cmd_dream(args)

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


def cmd_hive(args: argparse.Namespace) -> int:
    from pathlib import Path

    from hermescube import hive as hive_mod

    hive_root = args.hive or os.environ.get("HERMESCUBE_HIVE")
    if not hive_root:
        print("Error: hive path required (--hive or HERMESCUBE_HIVE)", file=sys.stderr)
        return 1

    cmd = args.hive_command
    if cmd == "init":
        r = hive_mod.init_hive(hive_root)
        print(f"Hive ready: {r['root']}")
        print(f"  name: {r['meta'].get('name')}")
        return 0

    if cmd == "status":
        s = hive_mod.hive_status(hive_root)
        if not s.get("ok"):
            print(f"Error: {s.get('error')}", file=sys.stderr)
            return 1
        print(f"Hive: {s.get('name')}  ({s.get('root')})")
        print(f"  collective entries: {s.get('collective_entries')}")
        print(f"  souls registered:   {s.get('souls')}")
        print(f"  pending offerings:  {s.get('pending_offerings')}")
        if "charters" in s:
            cmd_owner = s.get("command") or "NONE (run: hermescube hq charter --role command …)"
            print(f"  charters:           {s.get('charters')}  (command: {cmd_owner})")
            print(f"  pending handoffs:   {s.get('pending_handoffs')}")
        if "interviews" in s:
            print(f"  interviews held:    {s.get('interviews')}")
        for a in s.get("agents") or []:
            print(f"    · {a}")
        return 0

    if cmd == "assimilate":
        r = hive_mod.assimilate_offerings(hive_root)
        print(
            f"Assimilated: files={r['files']} rows={r['rows']} "
            f"merged={r['merged']} dupes={r['dupes']} blocked={r['blocked']}"
        )
        return 0

    if cmd == "souls":
        souls = hive_mod.list_souls(hive_root)
        if not souls:
            print("No souls registered yet.")
            return 0
        for s in souls:
            soul = s.get("soul") or {}
            growth = s.get("growth") or {}
            gstrip = ""
            if growth:
                age = growth.get("age") or {}
                age_s = age.get("label") or (
                    f"C{growth.get('cycles', 0)} · {growth.get('lived', '?')}"
                )
                era_s = growth.get("era_label") or growth.get("era") or "Cube of Eden"
                gstrip = (
                    f"  v{growth.get('version')} · {age_s} · {era_s}"
                )
            print(f"— {s.get('agent_id')}  (entries: {s.get('entry_count')}){gstrip}")
            for w in (soul.get("wisdom") or [])[:2]:
                print(f"    wisdom: {w[:90]}")
            for m in (soul.get("missions") or [])[:2]:
                print(f"    mission: {m[:90]}")
            skills = growth.get("skills") or []
            if skills:
                print(f"    skills: {', '.join(skills[:4])}")
            if growth.get("capability") is not None or growth.get("strength") is not None:
                cap = growth.get("capability", growth.get("strength"))
                print(f"    capability: {cap}/100")
        return 0

    if cmd == "pilgrimage":
        home = args.hermes_home or os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
        agent = args.agent or os.environ.get("HERMES_PROFILE") or "hermes"
        r = hive_mod.pilgrimage(
            hive_root,
            hermes_home=home,
            agent_id=agent,
            focus=args.focus or "",
            interview=bool(args.interview),
            interview_peers=int(args.interview_peers or 1),
        )
        if not r.get("ok"):
            print(f"Error: {r.get('error')}", file=sys.stderr)
            return 1
        offer = r.get("offer") or {}
        draw = r.get("draw") or {}
        assim = r.get("assimilate") or {}
        print(f"Pilgrimage complete — agent '{agent}' → {hive_root}")
        print(f"  offered:     {offer.get('rows', 0)} distilled entries")
        print(f"  assimilated: {assim.get('merged', 0)} (dupes {assim.get('dupes', 0)}, blocked {assim.get('blocked', 0)})")
        print(f"  drew:        {draw.get('drawn', 0)} collective entries")
        print(f"  soul card:   {'updated' if r.get('soul_card') is True else r.get('soul_card')}")
        for ivr in r.get("interviews") or []:
            if isinstance(ivr, dict) and ivr.get("ok"):
                mint = ivr.get("mint") or {}
                print(
                    f"  interview:   {ivr.get('session_id')} → {ivr.get('outcome')} "
                    f"(draft: {mint.get('name') or 'none'})"
                )
            elif isinstance(ivr, dict):
                print(f"  interview:   error: {ivr.get('error')}")
        g = r.get("growth") or {}
        age = g.get("age") or {}
        if g.get("bumped"):
            print(
                f"  growth:      v{g.get('from')} → v{g.get('to')}  "
                f"· {age.get('label', '')} · {g.get('era_label') or g.get('era')} "
                f"· capability {g.get('capability', g.get('strength'))}/100"
            )
        elif g.get("version"):
            print(
                f"  growth:      v{g.get('version')}  "
                f"· {age.get('label', '')} · {g.get('era_label') or g.get('era')} "
                f"· capability {g.get('capability', g.get('strength'))}/100"
            )
        cur = r.get("curator") or {}
        refines = cur.get("refines") or []
        if refines:
            for rf in refines:
                print(
                    f"  curator:     refined skill {rf.get('skill')} "
                    f"{rf.get('from_version')} → {rf.get('to_version')}"
                )
        elif cur.get("forge") or cur.get("garden"):
            forge = cur.get("forge") or {}
            garden = cur.get("garden") or {}
            print(
                f"  curator:     era milestone — "
                f"forged={forge.get('forged', forge.get('written', 0))} "
                f"garden={garden.get('proposals', garden.get('surfaced', 0))}"
            )
        return 0

    print(f"Error: unknown hive command {cmd}", file=sys.stderr)
    return 1


def cmd_interview(args: argparse.Namespace) -> int:
    from pathlib import Path

    from hermescube import interview as iv

    hive_root = args.hive or os.environ.get("HERMESCUBE_HIVE")
    if not hive_root:
        print("Error: hive path required (--hive or HERMESCUBE_HIVE)", file=sys.stderr)
        return 1

    if args.interview_command == "list":
        items = iv.list_interviews(hive_root)
        if not items:
            print("No interviews yet.")
            return 0
        for i in items:
            print(
                f"[{i.get('status')}] {i.get('id')}  "
                f"{i.get('interviewer')} → {i.get('subject')}  "
                f"topic={i.get('topic')!r}  turns={i.get('turns')}  "
                f"outcome={i.get('outcome')}"
            )
        return 0

    if args.interview_command == "dialogue":
        interviewer = args.interviewer or os.environ.get("HERMES_PROFILE") or "hermes"
        if not args.subject:
            print("Error: --subject required", file=sys.stderr)
            return 1
        home = args.hermes_home or os.environ.get("HERMES_HOME") or str(
            Path.home() / ".hermes"
        )
        r = iv.peer_dialogue(
            hive_root,
            interviewer=interviewer,
            subject=args.subject,
            topic=args.topic,
            mode=args.mode,
            hermes_home=home,
            persist=not args.no_persist,
            mint=not args.no_mint,
        )
        if not r.get("ok"):
            print(f"Error: {r.get('error')}", file=sys.stderr)
            return 1
        print(f"Peer dialogue complete — {interviewer} interviewed {args.subject}")
        print(f"  session:  {r.get('session_id')}")
        print(f"  turns:    {r.get('turns')}")
        print(f"  outcome:  {r.get('outcome')}")
        print(f"  brief:    {r.get('brief_path')}")
        print(f"  persisted to hive: {r.get('persisted')}")
        mint = r.get("mint") or {}
        if mint.get("ok"):
            print(f"  skill draft: {mint.get('draft')}  (pending — promote to install)")
        elif mint:
            print(f"  mint: {mint.get('error') or mint}")
        return 0

    print(f"Error: unknown interview command {args.interview_command}", file=sys.stderr)
    return 1


def cmd_hq(args: argparse.Namespace) -> int:
    from hermescube import hq as hq_mod

    hive_root = args.hive or os.environ.get("HERMESCUBE_HIVE")
    if not hive_root:
        print("Error: HQ path required (--hive or HERMESCUBE_HIVE)", file=sys.stderr)
        return 1
    cmd = args.hq_command

    if cmd == "charter":
        if not args.agent or not args.lane or not args.keywords:
            print("Error: --agent, --lane, --keywords required", file=sys.stderr)
            return 1
        r = hq_mod.register_charter(
            hive_root,
            args.agent,
            role=args.role,
            lane=args.lane,
            keywords=[k.strip() for k in args.keywords.split(",") if k.strip()],
            boundaries=[b.strip() for b in args.boundaries.split(";") if b.strip()],
        )
        if not r.get("ok"):
            print(f"Error: {r.get('error')}", file=sys.stderr)
            return 1
        c = r["charter"]
        print(f"Chartered [{c['role']}] {c['agent_id']}: {c['lane']}")
        return 0

    if cmd == "retire":
        if not args.agent:
            print("Error: --agent required", file=sys.stderr)
            return 1
        r = hq_mod.retire_charter(hive_root, args.agent)
        print(f"Retired: {args.agent}" if r.get("ok") else f"Error: {r.get('error')}")
        return 0 if r.get("ok") else 1

    if cmd == "list":
        charters = hq_mod.list_charters(hive_root, include_retired=True)
        if not charters:
            print("No charters. Register with: hermescube hq charter --agent ... --lane ... --keywords ...")
            return 0
        for c in charters:
            mark = "·" if c.get("status") == "active" else "✝"
            print(f"{mark} [{c.get('role')}] {c['agent_id']}: {c.get('lane')}")
            print(f"    keywords: {', '.join(c.get('keywords') or [])}")
            for b in c.get("boundaries") or []:
                print(f"    boundary: {b}")
        return 0

    if cmd == "route":
        if not args.task:
            print("Error: --task required", file=sys.stderr)
            return 1
        r = hq_mod.route_task(hive_root, args.task)
        if not r.get("ok"):
            print(f"Error: {r.get('error')}", file=sys.stderr)
            return 1
        print(f"Owner: {r['owner']}  (via {r['via']}, confidence {r['confidence']:.2f})")
        print(f"  lane: {r.get('lane')}")
        if r.get("runner_up"):
            print(f"  runner-up: {r['runner_up']}")
        return 0

    if cmd == "verify":
        r = hq_mod.verify_fleet(hive_root)
        print(f"Fleet verdict: {r['verdict']}  (charters: {r['charters']})")
        for f in r.get("findings") or []:
            print(f"  ! {f['flag']}: {f['detail']}")
        return 0 if r["verdict"] == "healthy" else 2

    if cmd == "freeze":
        r = hq_mod.freeze_baseline(hive_root)
        b = r["baseline"]
        print(f"Baseline frozen: {len(b['charters'])} charters, "
              f"collective entries {b['collective_entries']}")
        return 0

    if cmd == "drift":
        r = hq_mod.verify_baseline(hive_root)
        if not r.get("ok"):
            print(f"Error: {r.get('error')}", file=sys.stderr)
            return 1
        if r["clean"]:
            print("No drift since baseline.")
            return 0
        print("Drift detected:")
        for d in r["drift"]:
            print(f"  ! {d}")
        return 2

    if cmd == "handoffs":
        hs = hq_mod.list_handoffs(hive_root, limit=20)
        if not hs:
            print("No handoffs recorded.")
            return 0
        for h in hs:
            print(f"[{h.get('status')}] {h.get('id')}  "
                  f"{h.get('from_agent')} → {h.get('to_agent')}: "
                  f"{h.get('task', '')[:70]}")
        return 0

    if cmd == "complete":
        if not args.id:
            print("Error: --id required (handoff id)", file=sys.stderr)
            return 1
        r = hq_mod.update_handoff_status(hive_root, args.id, "completed")
        if not r.get("ok"):
            print(f"Error: {r.get('error')}", file=sys.stderr)
            return 1
        print(f"Handoff settled: {args.id} → completed")
        return 0

    print(f"Error: unknown hq command {cmd}", file=sys.stderr)
    return 1


def cmd_blackbox(args: argparse.Namespace) -> int:
    """Flight recorder — Cube center blackbox organ (capture / prove / verify)."""
    import json
    from pathlib import Path

    from hermescube import center
    from hermescube.blackbox import load_record, verify_integrity

    home = args.hermes_home or os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    cmd = args.bb_command

    if cmd == "status":
        st = center.center_status(hermes_home=home)
        bb = (st.get("organs") or {}).get("blackbox") or {}
        print(f"Center API {st.get('api_version')} · blackbox organ")
        print(f"  {bb.get('organ')}: {bb.get('job')}")
        print(f"  api: {bb.get('api')}")
        print(f"  heart_ready: {(st.get('heart') or {}).get('heart_ready')}")
        return 0

    if cmd == "capture":
        out = center.flight_capture(
            session_id=args.session,
            latest=bool(args.latest or not args.session),
            hermes_home=home,
            redact=not args.no_redact,
            out_path=args.out,
        )
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 1

    if cmd == "prove":
        if not args.claim:
            print("Error: --claim required", file=sys.stderr)
            return 1
        out = center.flight_prove(
            args.claim,
            record_path=args.record,
            hermes_home=home,
            session_id=args.session,
            latest=bool(args.latest or not args.session),
        )
        print(json.dumps(out, indent=2, default=str))
        if args.out:
            Path(args.out).write_text(json.dumps(out, indent=2, default=str) + "\n")
        return int(out.get("exit_code_hint", 1 if not out.get("ok") else 0))

    if cmd == "verify":
        if not args.record:
            print("Error: --record PATH required", file=sys.stderr)
            return 1
        rec = load_record(args.record)
        ok = verify_integrity(rec)
        print(json.dumps({"ok": ok, "record_id": rec.id, "events": len(rec.events)}, indent=2))
        return 0 if ok else 2

    if cmd == "breathe":
        out = center.breathe(
            hermes_home=home,
            session_id=args.session,
            latest=bool(args.latest or not args.session),
        )
        # drop huge nested sealed payloads for CLI readability
        slim = {
            "ok": out.get("ok"),
            "elapsed_ms": out.get("elapsed_ms"),
            "idea": out.get("idea"),
            "inhale": out.get("phases", {}).get("inhale"),
            "gas_exchange": {
                k: v
                for k, v in (out.get("phases", {}).get("gas_exchange") or {}).items()
                if k != "claims"
            },
            "claims": (out.get("phases", {}).get("gas_exchange") or {}).get("claims"),
            "exhale": {
                "sealed_ok": (out.get("phases", {}).get("exhale") or {}).get("sealed_ok"),
                "relations": (out.get("phases", {}).get("exhale") or {}).get("relations"),
                "breath_note": (out.get("phases", {}).get("exhale") or {}).get("breath_note"),
            },
            "error": out.get("error"),
        }
        print(json.dumps(slim, indent=2, default=str))
        if args.out:
            Path(args.out).write_text(json.dumps(out, indent=2, default=str) + "\n")
        return 0 if out.get("ok") else 1

    print(f"Error: unknown blackbox command {cmd}", file=sys.stderr)
    return 1


def cmd_checkpoint(args: argparse.Namespace) -> int:
    """Safe-lock ark — flash clone of cube book + core identity."""
    import json
    from pathlib import Path

    from hermescube import checkpoint as ck

    home = args.hermes_home or os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    cmd = args.ck_command

    if cmd == "list":
        rows = ck.list_checkpoints(home)
        print(json.dumps({"ok": True, "checkpoints": rows}, indent=2))
        return 0

    if cmd == "create":
        out = ck.create_checkpoint(
            args.name,
            hermes_home=home,
            label=args.label or "",
            include_dense=bool(args.dense),
            pack_tar=not bool(args.no_tar),
        )
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1

    if cmd == "restore":
        if not args.name:
            print("Error: --name SLUG required for restore", file=sys.stderr)
            return 1
        identity = True
        cube = True
        if args.identity_only:
            cube = False
        if args.cube_only:
            identity = False
        out = ck.restore_checkpoint(
            args.name,
            hermes_home=home,
            restore_identity=identity,
            restore_cube=cube,
            restore_config=bool(args.with_config),
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1

    print(f"Error: unknown checkpoint command {cmd}", file=sys.stderr)
    return 1


def cmd_harness(args: argparse.Namespace) -> int:
    from pathlib import Path

    from hermescube import self_evolution as se

    home = args.hermes_home or os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    cmd = args.harness_command

    if cmd == "witness":
        if not args.desc:
            print("Error: --desc required (describe the real friction)", file=sys.stderr)
            return 1
        rec = se.record_witness(home, args.desc, severity=args.severity, kind="manual", source="cli")
        print(f"Witness recorded [{rec['severity']}]: {rec['description'][:100]}")
        return 0

    if cmd == "status":
        s = se.harness_status(home)
        print(f"Harness status ({home})")
        print(f"  open witnesses: {s['open_witnesses']}")
        p = s["predictions"]
        print(f"  predictions: open={p['open']} confirmed={p['confirmed']} "
              f"refuted={p['refuted']} expired={p['expired']}")
        lc = s.get("last_critique")
        if lc:
            print(f"  last critique: {lc['verdict']}")
            for f in lc.get("findings") or []:
                print(f"    ! {f['flag']}: {f['detail']}")
        for c in (s.get("recent_cycles") or [])[-5:]:
            print(f"  cycle [{c['kind']}] → {c['outcome']}")
        return 0

    if cmd == "critic":
        r = se.run_critic(home)
        print(f"Critic verdict: {r['verdict']} "
              f"(cycles reviewed: {r['cycles_reviewed']}, open witnesses: {r['open_witnesses']})")
        for f in r.get("findings") or []:
            print(f"  ! {f['flag']}: {f['detail']}")
        return 0

    if cmd == "verify":
        cube_path = Path(home) / "memories" / "memory.cube"
        cube = None
        if cube_path.is_file():
            from hermescube.cube import CubeFile

            cube = CubeFile.open(str(cube_path))
        try:
            stats = se.verify_predictions(home, cube=cube)
        finally:
            if cube is not None:
                cube.close()
        print(f"Verifier: open={stats['open']} confirmed={stats['confirmed']} "
              f"refuted={stats['refuted']} expired={stats['expired']}")
        return 0

    if cmd == "gardener":
        cube_path = Path(home) / "memories" / "memory.cube"
        if not cube_path.is_file():
            print(f"Error: cube missing: {cube_path}", file=sys.stderr)
            return 1
        from hermescube.cube import CubeFile

        with CubeFile.open(str(cube_path)) as cube:
            r = se.run_gardener(cube, home)
        print(f"Gardener: scanned {r['durable_scanned']} durable entries, "
              f"{len(r['dormant_candidates'])} dormant candidates")
        for c in r["dormant_candidates"][:10]:
            print(f"  · [{c['type']}] {c['description'][:80]} "
                  f"(trust {c['trust']:.2f}, {c['age_days']}d)")
        if r["dormant_candidates"]:
            print("  (proposals only — archive via hermescube_manage remove)")
        return 0

    print(f"Error: unknown harness command {cmd}", file=sys.stderr)
    return 1


def cmd_dream(args: argparse.Namespace) -> int:
    """CubeDream CLI — soul solo + hive circle (dream together)."""
    from pathlib import Path

    from hermescube import dream as dream_mod
    from hermescube import dream_circle as circle_mod
    from hermescube.cube import CubeFile
    from hermescube.hive import init_hive, is_hive

    home = Path(
        args.hermes_home
        or os.environ.get("HERMES_HOME")
        or (Path.home() / ".hermes")
    )
    agent = args.agent or os.environ.get("HERMES_PROFILE") or "hermes"
    cmd = args.dream_command

    if cmd == "status":
        st = dream_mod.dream_status(home)
        print(f"CubeDream L1 — mode={st.get('mode')} due={st.get('due')}")
        for r in st.get("reasons") or []:
            print(f"  · {r}")
        print(f"  diary: {st.get('diary')}")
        hive = args.hive or os.environ.get("HERMESCUBE_HIVE")
        if hive:
            circles = circle_mod.list_circles(hive, limit=8)
            print(f"Circles at {hive}: {len(circles)}")
            for c in circles:
                print(
                    f"  · [{c.get('status')}] {c.get('circle_id')} "
                    f"members={len(c.get('members') or [])} "
                    f"topic={c.get('topic')!r}"
                )
        return 0

    if cmd == "solo":
        cube_path = home / "memories" / "memory.cube"
        if not cube_path.is_file():
            print(f"Error: cube missing: {cube_path}", file=sys.stderr)
            return 1
        with CubeFile.open(str(cube_path)) as cube:
            from hermescube.engram_net import EngramNet
            from hermescube.framework.paths import resolve_cube_paths

            paths = resolve_cube_paths(home)
            engram = EngramNet(paths.engram)
            report = dream_mod.run_solo_dream(
                cube,
                home,
                engram=engram,
                apply=bool(args.apply),
                dry_crystalize=not bool(args.commit_crystalize),
            )
        print(f"Soul dream {report.get('run_id')} applied={report.get('applied')}")
        print(f"  diary: {report.get('diary')}")
        if report.get("sleep_replay"):
            print(f"  sleep_replay: {report['sleep_replay']}")
        if report.get("crystalize"):
            print(f"  crystalize: {report['crystalize']}")
        return 0

    if cmd == "propose":
        cube_path = home / "memories" / "memory.cube"
        if cube_path.is_file():
            with CubeFile.open(str(cube_path)) as c:
                report = dream_mod.propose_memory_md(home, cube=c)
        else:
            report = dream_mod.propose_memory_md(home, cube=None)
        print(f"L4 proposals: {len(report.get('proposals') or [])} (not applied)")
        print(f"  path: {report.get('path')}")
        for p in (report.get("proposals") or [])[:5]:
            print(f"  · {p.get('line', '')[:90]}")
        return 0

    if cmd == "auto-circle":
        hive = args.hive or os.environ.get("HERMESCUBE_HIVE")
        if not hive:
            print("Error: --hive or HERMESCUBE_HIVE required", file=sys.stderr)
            return 1
        if not is_hive(hive):
            init_hive(hive)
        homes: dict[str, str] = {agent: str(home)}
        for spec in args.peer_home or []:
            if ":" not in spec:
                continue
            aid, path = spec.split(":", 1)
            homes[aid.strip()] = path.strip()
        pairs: list[tuple[str, str]] = []
        if args.interview_pair and ":" in args.interview_pair:
            a, b = args.interview_pair.split(":", 1)
            pairs.append((a.strip(), b.strip()))
        report = circle_mod.run_auto_circle(
            hive,
            agent_homes=homes,
            topic=args.topic or "night chorus",
            opened_by=agent,
            interview_pairs=pairs or None,
            skim=not bool(args.no_skim),
        )
        print(json.dumps(report, indent=2, default=str)[:4000])
        return 0 if report.get("ok") else 1

    if cmd == "circle":
        hive = args.hive or os.environ.get("HERMESCUBE_HIVE")
        if not hive:
            print("Error: --hive or HERMESCUBE_HIVE required", file=sys.stderr)
            return 1
        if not is_hive(hive):
            init_hive(hive)
        sub = args.circle_command or "list"
        if sub == "list":
            for c in circle_mod.list_circles(hive):
                print(
                    f"[{c.get('status')}] {c.get('circle_id')} "
                    f"members={c.get('members')} topic={c.get('topic')!r}"
                )
            return 0
        if sub == "open":
            r = circle_mod.open_circle(hive, opened_by=agent, topic=args.topic or "")
            print(f"Opened circle {r.get('circle_id')} topic={r.get('topic')!r}")
            return 0 if r.get("ok") else 1
        cid = args.id
        if sub != "open" and not cid and sub not in ("list",):
            print("Error: --id required", file=sys.stderr)
            return 1
        if sub == "join":
            r = circle_mod.join_circle(hive, cid, agent_id=agent)
            print(json.dumps(r, indent=2, default=str))
            return 0 if r.get("ok") else 1
        if sub == "status":
            r = circle_mod.circle_status(hive, cid)
            print(json.dumps(r, indent=2, default=str))
            return 0 if r.get("ok") else 1
        if sub == "signal":
            if args.content:
                r = circle_mod.post_signal(
                    hive, cid, agent_id=agent, summary=args.content
                )
            else:
                cube_path = home / "memories" / "memory.cube"
                if not cube_path.is_file():
                    print(f"Error: cube missing: {cube_path}", file=sys.stderr)
                    return 1
                with CubeFile.open(str(cube_path)) as cube:
                    r = circle_mod.signal_from_cube(
                        hive, cid, cube, agent_id=agent
                    )
            print(json.dumps(r, indent=2, default=str))
            return 0 if r.get("ok") else 1
        if sub == "score":
            r = circle_mod.score_circle(hive, cid, scorer=agent)
            print(
                f"Scored: signals={r.get('signals')} candidates={r.get('candidates')} "
                f"together={r.get('together_count')}"
            )
            for t in r.get("top") or []:
                mark = "★" if t.get("together") else "·"
                print(f"  {mark} {t.get('score')}  {t.get('summary', '')[:70]}")
            return 0 if r.get("ok") else 1
        if sub == "dialogue":
            subject = args.subject or ""
            if not subject:
                print("Error: --subject required", file=sys.stderr)
                return 1
            r = circle_mod.dialogue_in_circle(
                hive,
                cid,
                interviewer=agent,
                subject=subject,
                topic=args.topic or "",
                hermes_home=home,
                mint=False,
            )
            print(json.dumps(r, indent=2, default=str)[:3000])
            return 0 if r.get("ok") else 1
        if sub == "skim":
            r = circle_mod.adversarial_skim(hive, cid)
            print(
                f"Adversarial skim: flagged={r.get('flagged')}/{r.get('candidates')}"
            )
            return 0 if r.get("ok") else 1
        if sub == "close":
            r = circle_mod.close_circle(hive, cid, closer=agent)
            print(json.dumps(r, indent=2, default=str))
            return 0 if r.get("ok") else 1
        if sub == "draw":
            cube_path = home / "memories" / "memory.cube"
            if not cube_path.is_file():
                print(f"Error: cube missing: {cube_path}", file=sys.stderr)
                return 1
            with CubeFile.open(str(cube_path)) as cube:
                r = circle_mod.draw_circle(hive, cid, cube, agent_id=agent)
            print(json.dumps(r, indent=2, default=str))
            return 0 if r.get("ok") else 1
        print(f"Error: unknown circle command {sub}", file=sys.stderr)
        return 1

    print(f"Error: unknown dream command {cmd}", file=sys.stderr)
    return 1


def cmd_dense(args: argparse.Namespace) -> int:
    """Export/import portable dense text archives (no float vectors)."""
    import os
    from pathlib import Path

    from hermescube.dense import export_dense, import_dense_into_cube

    home = Path(
        args.hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")
    )
    cube = Path(args.cube) if args.cube else (home / "memories" / "memory.cube")
    out = (
        Path(args.out)
        if args.out
        else (home / "memories" / "memory.dense.jsonl.gz")
    )
    cmd = args.dense_command
    if cmd == "stats":
        if not cube.is_file():
            print(f"cube missing: {cube}", file=sys.stderr)
            return 1
        with CubeFile.open(str(cube)) as c:
            dens = c.density_stats()
        print("HermesCube density")
        print(f"  cube: {cube}")
        print(f"  entries: {dens.get('entries')}")
        print(
            f"  text+data: {dens.get('text_plus_data_share_pct')}% · "
            f"vectors≈{dens.get('vector_share_pct')}%"
        )
        print(f"  recommendation: {dens.get('recommendation')}")
        print(f"  note: {dens.get('note')}")
        return 0
    if cmd == "export":
        if not cube.is_file():
            print(f"cube missing: {cube}", file=sys.stderr)
            return 1
        r = export_dense(cube, out)
        print(
            f"exported {r.get('entries')} entries → {r.get('path')} "
            f"({r.get('out_bytes')} bytes, ratio={r.get('compression_ratio'):.1f}x)"
        )
        return 0
    if cmd == "import":
        if not out.is_file():
            # allow --out as the dense source for import
            src = out
            print(f"dense archive missing: {src}", file=sys.stderr)
            return 1
        n = import_dense_into_cube(out, cube, create=True)
        print(f"imported {n} entries into {cube}")
        return 0
    print(f"unknown dense command: {cmd}", file=sys.stderr)
    return 1


def cmd_setup(args: argparse.Namespace) -> int:
    from hermescube import connect as cx

    r = cx.setup(
        hermes_home_override=args.hermes_home,
        run_install_script=not bool(args.no_install_script),
    )
    print(cx.format_connect(r.get("connect") or {}))
    if r.get("install") and not r["install"].get("skipped"):
        print("\ninstall:", "ok" if r["install"].get("ok") else "issues")
        tail = (r["install"].get("log_tail") or "")[-500:]
        if tail and not r["install"].get("ok"):
            print(tail)
    return 0 if r.get("ok") else 1


def cmd_connect(args: argparse.Namespace) -> int:
    from hermescube import connect as cx

    r = cx.connect(
        hermes_home_override=args.hermes_home,
        ensure_plugin=not bool(args.no_plugin),
    )
    print(cx.format_connect(r))
    return 0 if r.get("ok") else 1


def cmd_status(args: argparse.Namespace) -> int:
    import json

    from hermescube import connect as cx

    s = cx.status_report(args.hermes_home)
    if args.json:
        print(json.dumps(s, indent=2, default=str))
    else:
        print(cx.format_status(s))
    return 0 if s.get("ok") else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    import os
    from pathlib import Path

    home = Path(args.hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    cube = home / "memories" / "memory.cube"
    plugin = home / "plugins" / "hermescube"
    cfg = home / "config.yaml"
    identity = str(getattr(args, "identity", "") or "").strip()
    workspace = str(getattr(args, "workspace", "") or "").strip()
    nest = bool(identity and workspace)
    path_kw = {
        "agent_identity": identity,
        "agent_workspace": workspace,
        "nest_profiles": nest,
    }
    print("HermesCube doctor")
    print(f"  HERMES_HOME: {home}")
    print(f"  cube:        {cube}  {'EXISTS' if cube.is_file() else 'missing (ok until first use)'}")
    print(f"  plugin dir:  {plugin}  {'OK' if (plugin / '__init__.py').is_file() else 'MISSING'}")
    print(f"  config:      {cfg}  {'OK' if cfg.is_file() else 'MISSING'}")
    if nest:
        print(f"  profile nest: identity={identity} workspace={workspace}")
    provider = None
    plugin_cfg: dict = {}
    if cfg.is_file():
        try:
            import yaml
            c = yaml.safe_load(cfg.read_text()) or {}
            provider = (c.get("memory") or {}).get("provider")
            plugin_cfg = ((c.get("plugins") or {}).get("hermescube") or {})
        except Exception as e:
            print(f"  config parse error: {e}")
    print(f"  memory.provider: {provider or '(unset)'}")
    if plugin_cfg:
        print(
            f"  plugins.hermescube: policy={plugin_cfg.get('memory_policy', '(unset)')} "
            f"auto_extract={plugin_cfg.get('auto_extract', '(unset)')}"
        )
    try:
        import hermescube
        print(f"  package: {hermescube.__version__} @ {hermescube.__file__}")
        # Version skew: installed package vs plugin tree manifest
        man = plugin / "plugin.yaml"
        if not man.is_file():
            man = plugin / "plugin" / "plugin.yaml"
        if man.is_file():
            try:
                import yaml

                mv = str((yaml.safe_load(man.read_text()) or {}).get("version") or "")
                if mv and mv != hermescube.__version__:
                    print(
                        f"  ! version skew: package={hermescube.__version__} "
                        f"plugin.yaml={mv} — run hermescube update"
                    )
                else:
                    print(f"  versions: package=plugin.yaml={hermescube.__version__}")
            except Exception as e:
                print(f"  plugin.yaml: unreadable ({e})")
    except Exception as e:
        print(f"  package: NOT IMPORTABLE ({e})")
        return 1
    # Ship layout stamps
    origin = plugin / ".hermescube-origin"
    pin = plugin / ".hermescube-source-root"
    if (plugin / ".git").is_dir():
        print("  ship layout: git checkout (hermes plugins update OK)")
    elif pin.is_file():
        print(f"  ship layout: pinned source → {pin.read_text().strip()}")
    elif origin.is_file():
        print(f"  ship layout: origin stamp → {origin.read_text().strip()}")
        print("               hermescube update fetches via cache")
    else:
        print("  ship layout: copy (run install_hermes.sh to stamp origin)")
    if provider != "hermescube":
        print("  hint: hermes config set memory.provider hermescube")
        print("        or: ./scripts/install_hermes.sh --from-git")
    print("  update: hermescube update   # code only — never wipes cube")
    # Live cube integrity (real data check)
    if cube.is_file():
        try:
            with CubeFile.open(str(cube)) as c:
                integ = c.integrity_check()
                ents = list(c.read_l1() or [])
            print("  integrity:")
            print(f"    ok={integ.get('ok')} entries={integ.get('entries_read')} "
                  f"empty={integ.get('empty_descriptions')} "
                  f"dups={integ.get('duplicate_ids')} "
                  f"bad_vec={integ.get('bad_vectors')}")
            print(f"    bytes cube={integ.get('cube_bytes')} "
                  f"cubelog={integ.get('cubelog_bytes')}")
            for issue in integ.get("issues") or []:
                print(f"    ! {issue}")
            try:
                dens = c.density_stats()
                print(
                    f"  density: text+data={dens.get('text_plus_data_share_pct')}% "
                    f"vectors≈{dens.get('vector_share_pct')}% "
                    f"→ {dens.get('recommendation')}"
                )
            except Exception as e:
                print(f"  density: n/a ({e})")
            try:
                from hermescube.bootstrap import bootstrap_status

                bst = bootstrap_status(c, str(home))
                print(
                    f"  bootstrap: entries={bst.get('cube_entries')} "
                    f"needs_import={bst.get('needs_import')} "
                    f"skills={bst.get('skills_installed')} "
                    f"hint={bst.get('hint')}"
                )
            except Exception as e:
                print(f"  bootstrap: n/a ({e})")
            try:
                from hermescube.wisdom import functional_loop_stats

                loop = functional_loop_stats(ents)
                print(
                    f"  functional_loop: crystals={loop.get('crystal_count')} "
                    f"beliefs={loop.get('belief_count')} "
                    f"wisdom_ratio={loop.get('wisdom_ratio')} "
                    f"dup_pressure={loop.get('dup_pressure')} "
                    f"healthy={loop.get('healthy')}"
                )
            except Exception as e:
                print(f"  functional_loop: n/a ({e})")
            # Compounding surfaces (triage / relations / last growth merge)
            try:
                from hermescube.triage import load_plan, plan_path

                plan = load_plan(home, **path_kw)
                pp = plan_path(home, **path_kw)
                if plan:
                    cp = plan.get("control_plan") or {}
                    print(
                        f"  triage: focus={cp.get('next_focus')} "
                        f"counts={plan.get('counts')} path={pp}"
                    )
                else:
                    print(f"  triage: no plan yet ({pp})")
            except Exception as e:
                print(f"  triage: n/a ({e})")
            try:
                from hermescube.relations import RelationStore

                st = RelationStore(home, **path_kw).stats()
                print(
                    f"  relations: {st.get('relations')} "
                    f"(open={st.get('open')}) path={st.get('path')}"
                )
            except Exception as e:
                print(f"  relations: n/a ({e})")
            try:
                merges = [
                    e
                    for e in ents
                    if (getattr(e, "data", None) or {}).get("growth_merge")
                ]
                if merges:
                    last = merges[-1]
                    print(
                        f"  growth_merge: last_id={last.id} "
                        f"axes={(last.data or {}).get('axes')}"
                    )
                else:
                    print("  growth_merge: none yet")
            except Exception as e:
                print(f"  growth_merge: n/a ({e})")
            try:
                from hermescube.memory_gate import list_candidates, oasis_doctor_card
                from hermescube.cuboasis import progress_usefulness

                pend = list_candidates(str(home), status="pending", limit=5, **path_kw)
                print(
                    f"  candidates: pending={pend.get('count', 0)} "
                    f"path={pend.get('path')}"
                )
                useful = progress_usefulness(str(home), **path_kw).get("usefulness")
                print(f"  usefulness: {useful}")
                card = oasis_doctor_card(c, str(home), **path_kw)
                print(
                    f"  cuboasis_doctor: health={card.get('health')} "
                    f"pending={card.get('pending_candidates')} "
                    f"usefulness={card.get('usefulness')}"
                )
                for ch in (card.get("checks") or [])[:8]:
                    if ch.get("status") not in ("ok", "empty"):
                        print(
                            f"    ! {ch.get('name')}={ch.get('status')} "
                            f"{ch.get('detail')}"
                        )
            except Exception as e:
                print(f"  cuboasis_governance: n/a ({e})")
            if not integ.get("ok"):
                return 1
        except Exception as e:
            print(f"  integrity: FAIL ({e})")
            return 1
    else:
        print("  integrity: skip (no cube yet)")
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
