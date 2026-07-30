# Security suite — sealed library buildings

**Rule:** one `HERMES_HOME` → one book → **no cross-profile bleed**, no secret leakage.

## Generator isolation

| Boundary | Enforcement |
|----------|-------------|
| Path containment | All cube/checkpoint IO must resolve **under** `HERMES_HOME` |
| Profile separation | Each profile home has its own `memories/memory.cube` |
| Secrets | Never pack `.env` / `auth.json` / keys into checkpoints |
| Secret scan | Text files scanned before ark pack / restore |
| Permissions | `hermescube security harden` → 0700 vaults, 0600 books & identity |
| Git tree | `scripts/check_isolation.sh` — no operator paths / live cubes in repo |

## CLI

```bash
hermescube security audit          # findings for THIS HERMES_HOME
hermescube security harden         # tighten modes (best-effort)
hermescube security audit --json
```

`connect` / `checkpoint create` also harden after success.

## Profiles (pilots)

```bash
# Client A library — never touches default home
HERMES_HOME=~/.hermes/profiles/client-a hermescube connect
HERMES_HOME=~/.hermes/profiles/client-a hermescube security audit
HERMES_HOME=~/.hermes/profiles/client-a hermescube checkpoint create --name a-lock
```

Do **not** copy `memory.cube` between profile homes unless you intentionally merge libraries.

## Checkpoint safe locks

- Slug cannot contain `/` or `..`
- Sources validated with `validate_checkpoint_sources`
- Restore refuses forbidden rels and path escape
- Live files backed up as `*.pre-restore-*` before overwrite

## Full suite map

| Layer | Tool |
|-------|------|
| Door locks (modes) | `security harden` |
| Inspection | `security audit` |
| Flight redact | `blackbox` (redaction ON) |
| Identity ark | `checkpoint` (no .env) |
| Repo cleanliness | `scripts/check_isolation.sh` |
| Provider scope | `memory.provider` per home only |

## If audit fails

1. `hermescube security harden`  
2. Remove any `.env` from `memories/checkpoints/`  
3. `chmod 600` on `.env` and `memory.cube`  
4. Re-run `hermescube security audit`
