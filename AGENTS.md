# AGENTS.md

## Cursor Cloud specific instructions

HermesCube is a **pure-Python library + CLI** (`hermescube`, Python 3.11+). There are **no servers, ports, Docker, or web UI** — everything is in-process and file-based. "Running the app" means running the CLI or the test suite. Standard dev/test/lint commands live in `CONTRIBUTING.md` and `pyproject.toml`; ports/services do not apply.

- The package is installed editable (`pip install -e ".[dev]"`) by the startup update script, into the user site (`~/.local/bin`), which is **not on `PATH`**. So invoke tools by module rather than by console script:
  - Tests: `python3 -m pytest tests/ -q` (455 tests, ~15s)
  - Lint/type-check: `python3 -m pyright hermescube/` (or add `~/.local/bin` to `PATH` and run `pyright hermescube/`). Zero errors required.
  - CLI: `python3 -m hermescube <cmd>` (e.g. `init`, `append`, `query`, `info`, `dump`).
- The CLI reads/writes under `HERMES_HOME` (defaults to `~/.hermes`). When exercising the CLI, set `HERMES_HOME` to a throwaway dir (e.g. `HERMES_HOME=/tmp/hermes_demo`) so you never touch a real home. Runtime data (`*.cube`, `*.cubelog`, `*.embedder`, `memories/`) is git-ignored and must **never** be committed.
- `numpy` is an optional accelerator (auto-detected); the code has a pure-Python fallback. CI also runs a no-numpy matrix. The update script installs numpy via the `[dev]` extra.
