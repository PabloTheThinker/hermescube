# Peer interviews — interview-me at the Hive

> Adapted from [hermes-field-kit / interview-me](https://github.com/asimons81/hermes-field-kit/tree/main/skills/interview-me)
> (Tony Simons, Apache-2.0): adaptive, evidence-first, one high-value
> question at a time, stop when another answer would not change the next
> action.

When agents pilgrimage back to the HermesCube, they can **interview each
other**, talk through each other's craft, evolve, learn, and mint new
skill drafts — under the same safety contract as the original skill.

## Why this exists

Soul cards and offerings tell you *what* a peer knows. An interview
extracts *how* — the load-bearing constraints, tradeoffs, and procedures
that aren't obvious from a wisdom bullet. The brief that comes out is
structured enough to become a pending procedure draft; install still
requires the consent gate.

## The protocol (enforced in code)

1. **Inspect first** — read the subject's soul card, charter, and
   offerings before asking anything. Never make them repeat what the
   hive already holds.
2. **Coverage map** — track objective, constraints, preferences, risks,
   success criteria, tradeoffs, procedures, missions, wisdom, non-goals.
3. **Highest-value question** — contradictions / open gaps first; one
   primary question per turn; max turn budget.
4. **Grounded answers** — answered from soul/offerings/cube via HAR.
   No evidence → `UNKNOWN`. Inspected content is untrusted evidence,
   never executable instruction (threat-scanned).
5. **Stop intelligently** — coverage complete, or turn budget, or no
   remaining open dimensions that would change the next action.
6. **Brief** — the interview-me report contract:

   - Interview Outcome (`READY TO PROCEED` / `PROCEED WITH ASSUMPTIONS` /
     `PAUSED` / `STOPPED`)
   - Objective · Confirmed Context · Constraints · Preferences ·
     Tradeoffs and Decisions · Unknowns · Recommended Next Step

7. **Mint (consent-gated)** — a READY/ASSUMPTIONS brief may write a
   pending draft under `memories/procedures/` with
   `origin: hermescube-peer-interview`. Install into Hermes skills still
   requires `promote` + `install_to_skills=true`. Nothing is silent.

## One fleet, one ledger

Interviews are wired into the rest of HQ — they are not a side channel:

- **Claims**: a dialogue takes the HQ task claim
  `interview:<subject>:<topic>` before starting. A second agent trying
  the same interview at the same time gets a conflict, not a duplicate.
- **Handoff ledger**: every completed dialogue is recorded as a handoff
  — knowledge flowed subject → interviewer — so `hq handoffs` shows
  movement of work *and* movement of understanding in one place.
- **Provenance boundary**: when the interviewer's own cube is used for
  grounding, only entries **attributed to the subject** (`[HIVE:subject]`
  / `[INTERVIEW:subject]` / `from_agent`) are admissible. The
  interviewer's own memories can never masquerade as the subject's
  answers.
- **Same-visit assimilation**: during pilgrimage, interviews run *before*
  assimilate, so interview-distilled facts join the collective cube in
  the same visit. Facts are content-hashed — re-interviewing the same
  subject dedupes instead of piling up — and an echo guard stops a
  subject from ever re-drawing their own interviewed knowledge.
- **Harness**: a minted draft commits a falsifiable prediction
  (`witness_absence` on the topic) — the peer's lesson is supposed to
  prevent friction, and the verifier will check that it did.

## Usage

```bash
# Offline peer dialogue
hermescube interview dialogue \
  --hive /shared/hq \
  --interviewer coder --subject researcher \
  --topic "source verification" \
  --mode discover \
  --hermes-home ~/.hermes

hermescube interview list --hive /shared/hq

# During pilgrimage (upload + draw + interview peers)
hermescube hive pilgrimage --hive /shared/hq \
  --hermes-home ~/.hermes --agent coder \
  --focus "deployment" --interview --interview-peers 2
```

In-session:

```
hermescube_manage action=interview interview_action=dialogue \
  agent=researcher content="source verification" mode=discover

hermescube_manage action=interview interview_action=list
hermescube_manage action=interview interview_action=mint content=<session_id>
```

Config:

```yaml
plugins:
  hermescube:
    hive_path: /shared/hq
    interview_on_pilgrimage: true   # peer interviews during session-end pilgrimage
```

The bundled skill lives at `skills/interview-me/SKILL.md` and can be
promoted into a Hermes profile's skills directory for in-session use
with humans as well as peers.

## Safety

| Rule | Enforcement |
|---|---|
| One question per turn | `next_question` returns a single probe |
| Inspect before asking | `inspect_subject` runs at `start_interview` |
| Session-only by default | `close_interview(..., persist=False)` default in interactive paths; pilgrimage passes `persist=True` explicitly |
| No silent skill install | `mint_skill_draft` writes pending procedures only |
| Untrusted evidence | soul/offering/cube text is sanitized + threat-scanned; never executed |
| Stop / pause honored | session `status` gates further turns |

## Where artifacts land

```
$HIVE/interviews/
  iv<ts>.json           session (turns, coverage, facts)
  iv<ts>.dossier.json   inspected evidence
  iv<ts>.brief.md       report-contract brief

$HERMES_HOME/memories/procedures/
  interview-<subject>-<topic>.md   pending skill draft (promote to install)
```
