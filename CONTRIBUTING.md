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

```
hermescube/
├── hermescube/          # Core library
│   ├── __init__.py       # Public API exports
│   ├── __main__.py       # python -m hermescube
│   ├── cli.py            # CLI entrypoint (7 commands)
│   ├── hrr.py            # HRR algebra (numpy / pure-Python dual backend)
│   ├── cube.py           # .cube binary file I/O
│   ├── har.py            # HAR query engine + k-means
│   ├── embed.py          # Learned embeddings (TF-IDF + projection)
│   ├── provider.py       # CubeMemoryProvider (HermesAgent ABC)
│   ├── threats.py        # Prompt injection scanning
│   └── py.typed          # PEP 561 marker
├── plugin/               # HermesAgent plugin registration
│   ├── __init__.py
│   ├── cli.py
│   └── plugin.yaml
├── tests/                # Pytest test suite
│   ├── test_cube.py       # 25 tests — cube I/O, concurrency, edge cases
│   ├── test_har.py        # 14 tests — HAR queries, k-means, β updates
│   ├── test_hrr.py        # 17 tests — HRR algebra correctness
│   ├── test_embed.py      # 13 tests — learned embeddings + persistence
│   ├── test_provider.py   # 75 tests — provider ABC, tools, lifecycle
│   └── test_cli.py        # 14 tests — all CLI commands
├── benchmarks/           # HAR vs linear scan performance
├── docs/                 # Documentation
│   ├── SPEC.md            # Binary format specification
│   ├── ARCHITECTURE.md    # Design rationale
│   ├── API_REFERENCE.md   # Full API reference
│   └── USER_GUIDE.md      # How-to guides
├── pyproject.toml        # Package config + pyright + pytest settings
├── CHANGELOG.md
├── LICENSE
└── README.md
```

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
