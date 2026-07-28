# AGENTS.md

HermesCube is a **pure-Python library + CLI + Hermes MemoryProvider plugin** (Python 3.11+).  
No servers, ports, Docker, or web UI — in-process and file-based.

**Orient first:** [ABOUT.md](ABOUT.md) · [PURPOSE.md](PURPOSE.md) · [docs/CODEMAP.md](docs/CODEMAP.md) · [docs/ASSESSMENT.md](docs/ASSESSMENT.md).

## Dev / test

Standard commands live in `CONTRIBUTING.md` and `pyproject.toml`.

- Package often lands in user site (`~/.local/bin` may be off `PATH`). Prefer modules:
  - Tests: `python3 -m pytest tests/ -q` (~466 tests)
  - Types: `python3 -m pyright hermescube/` (zero errors)
  - CLI: `python3 -m hermescube <cmd>`
- Set `HERMES_HOME` to a throwaway dir when exercising the CLI so you never touch a real home.
- Runtime data (`*.cube`, `*.cubelog`, `*.embedder`, `memories/`) is git-ignored — **never commit**.
- `numpy` is optional (pure-Python fallback). CI runs a no-numpy matrix.
- Dual `plugin.yaml` (root + `plugin/`) must stay identical — `scripts/check_isolation.sh`.

## Edit rules

1. Peel manage/dream/tools into focused modules; do not re-inflate `provider.py`.  
2. User memory only under `$HERMES_HOME/memories/`.  
3. CubeDream must not auto-apply MEMORY.md diffs.  
4. Solo path first; hive/HQ/circles are opt-in.
