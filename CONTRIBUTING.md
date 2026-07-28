# Contributing

Thanks for your interest in HermesCube.

---

## Setup

```bash
git clone https://github.com/PabloTheThinker/hermescube.git
cd hermescube
pip install -e ".[dev]"
```

This installs hermescube in editable mode with numpy, pytest, pytest-cov,
and pyright.

### Dogfood against a real Hermes home

```bash
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
./scripts/install_hermes.sh
hermescube doctor
```

**Never** commit `*.cube` / user memory files. Runtime data belongs only under
`$HERMES_HOME/memories/`. End-user install:

```text
hermes plugins install PabloTheThinker/hermescube
→ $HERMES_HOME/plugins/hermescube/   (code)
→ $HERMES_HOME/memories/memory.cube  (their data)
```

### Isolation — no cross-pollution (mandatory)

| Allowed in **git repo** | Forbidden in **git repo** |
|-------------------------|---------------------------|
| Library code, tests, public docs, benches *scripts* | Any operator home paths (`/home/ilo`, `~/.ilo`, …) |
| Synthetic fixtures under `tests/` | Live `memory.cube`, `engram_net.json`, `yield_gradient.json`, journey ledgers |
| Generic examples using `$HERMES_HOME` | Personal MEMORY.md, client names, Tailscale, secrets |
| Lab *results* only if scrubbed/public | ILO/Vektra internal ops dumps |

**Install / update for the running agent (ILO or any host):**

```bash
# always prefer
hermescube update
# or
cd "$HERMES_HOME/plugins/hermescube" && ./scripts/update.sh
```

- **Do not** copy ad-hoc files from an operator tree into the public repo “to fix prod.”
- **Do not** `pip install -e` a polluted path as the ship source of truth.
- Experiments live under `$HERMES_HOME/hermescube-lab/` (or outside the repo) — never merge lab debris into `main`.
- After code lands on `main`: **`hermescube update`** on each host so plugins stay in sync without hand-merging.

Pre-commit / CI helper:

```bash
./scripts/check_isolation.sh
```

---

## Running Tests

```bash
# Full suite (200+ tests)
pytest

# Specific test file
pytest tests/test_cube.py

# Verbose output
pytest -v

# With coverage
pytest --cov=hermescube --cov-report=term-missing
```

All tests must pass before submitting a PR.

---

## Type Checking

```bash
pyright hermescube/
```

Zero errors required. The pyright config lives in `pyproject.toml`:

```toml
[tool.pyright]
include = ["hermescube"]
typeCheckingMode = "basic"
reportOptionalMemberAccess = false
reportInvalidTypeForm = false
```

These suppressions exist because numpy is optional — variables used in type
expressions with numpy types can't be fully resolved without it installed.

---

## Project Structure

High-level layout:

```
hermescube/
├── ABOUT.md · PURPOSE.md · README.md
├── hermescube/           # Library + CLI + MemoryProvider (see docs/CODEMAP.md)
├── plugin/               # Hermes register(ctx) + dual plugin.yaml
├── skills/               # operate · import · interview-me
├── docs/                 # Guides + docs/assets/ + CODEMAP.md
├── tests/                # pytest (~466)
├── scripts/              # install · update · check_isolation
└── benchmarks/
```

**Where to edit what:** [docs/CODEMAP.md](docs/CODEMAP.md).  
Prefer peeling new manage/dream/tools surfaces into focused modules over growing `provider.py`.

---

## Code Conventions

### Style

- Follow existing patterns in neighboring files
- No comments unless the code isn't self-documenting
- Type annotations on all public methods
- `from __future__ import annotations` at the top of every file

### Numpy Dual-Backend Pattern

Every vector operation must work with and without numpy. The pattern:

```python
def some_op(v: Array) -> Array:
    if hrr.has_numpy():
        import numpy as _np
        arr = _np.asarray(v, dtype=_np.float64)
        return _do_numpy_op(arr)
    return _do_pure_op(list(v))
```

Importing numpy inside the function prevents import errors when it's not
installed. Always use `dtype=_np.float64` for consistency.

### The `_unlocked` Suffix

Methods ending in `_unlocked` assume the caller holds `self._lock`. Public
methods acquire the lock, then call the `_unlocked` version. This prevents
accidental double-locking (RLock is reentrant but the pattern keeps intent
clear).

### Entry Layout: Single Source of Truth

The on-disk L1 entry layout is defined in exactly two places:
- `_pack_entry_bytes()` — serializes an entry to bytes (writer)
- `_read_entry_at()` — parses bytes back to an entry (reader)

Both use `_compute_entry_size()` for the byte size. Any format change must
update all three functions together.

---

## Adding Features

### Adding a new entry type

1. Add to `ENTRY_TYPES` dict in `cube.py`
2. The `ENTRY_TYPE_NAMES` reverse mapping is auto-generated
3. Update `get_tool_schemas()` enum lists in `provider.py`
4. Add a test in `tests/test_cube.py::TestEdgeCases::test_all_entry_types`
5. Update the entry types table in `README.md`

### Adding a new HRR operation

1. Add numpy implementation as `_numpy_<op>()` in `hrr.py`
2. Add pure-Python implementation as `_pure_<op>()`
3. Add public function that dispatches to both
4. Export from `__init__.py` and add to `__all__`
5. Add tests in `tests/test_hrr.py`

### Adding a new provider lifecycle hook

1. Add the method to `CubeMemoryProvider` in `provider.py`
2. Follow the HermesAgent `MemoryProvider` ABC signature exactly
3. Add tests in `tests/test_provider.py`
4. Update the provider docstring with the hook name

---

## Pull Request Guidelines

1. **Tests required.** New features need tests. Bug fixes need regression tests.
2. **Keep it focused.** One concern per PR.
3. **Run the full suite.** `pytest && pyright hermescube/` must pass.
4. **Update CHANGELOG.md.** Add an entry under the `## [Unreleased]` section.
5. **No breaking changes** to the `.cube` binary format without a version bump
   and backwards-compatibility code.

---

## Release Process

1. Update `__version__` in `hermescube/__init__.py`
2. Update `version` in `pyproject.toml`
3. Update `version` in `plugin/plugin.yaml`
4. Move `[Unreleased]` section to a dated release in `CHANGELOG.md`
5. Tag the release: `git tag v0.3.0`
6. Push: `git push --tags`

---

## Questions?

Open an issue on [GitHub Issues](https://github.com/PabloTheThinker/hermescube/issues).
