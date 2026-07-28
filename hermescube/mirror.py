"""Mirror layer — interconnected cube memory (infinite void co-activation).

Cube-native interconnect (not a port of upstream holographic):
- Entity extract (hygiene-first)
- Entity → entry index
- mirror_expand: co-entity + causal parents + optional colony trail boost

Hot path stays local — no LLM.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any, Iterable

from hermescube import bio_rank

_RE_MULTI_CAP = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
_RE_DOLLAR = re.compile(r"\$[A-Z_][A-Z0-9_]*(?:/[A-Za-z0-9_./-]+)?")
_RE_QUOTE = re.compile(r"[\"']([^\"']{2,40})[\"']")
_RE_EQUALS_NAME = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\s*="
)
# Machine-shaped identifiers — the vocabulary real agent memories are full of
# (service names, hosts, config keys, file names).
_RE_HYPHEN_ID = re.compile(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+\b")   # auth-service, eu-west
_RE_DOTTED_ID = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+\b")  # memory.cube
_RE_SNAKE_ID = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")    # payment_pipeline
_RE_CAMEL = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b")          # AuthService
_RE_CAP_TOKEN = re.compile(r"\b[A-Z][a-zA-Z0-9]{2,}\b")             # Grafana, Alice
# A capitalized word that opens a sentence is usually just a verb ("Deployed
# the …"), so single caps in that position need the inflection filter below.
_RE_SENT_START = re.compile(r"(?:^|(?<=[.!?])\s+|\n\s*)")
_VERBISH_SUFFIX = ("ed", "ing", "es")

# Never promote these as entities (noise that broke colony trails)
_STOP_ENT = frozenset({
    "the", "this", "that", "with", "from", "when", "what", "where", "who",
    "user", "hermes", "true", "false", "none", "path", "prefers", "short",
    "under", "after", "before", "until", "client", "cash", "primary",
    "human", "for", "and", "mission", "zero", "collect", "board", "exit",
    "pay", "verified", "offers", "dollars", "packages", "general", "memory",
    "system", "agent", "entry", "type", "file", "home", "open", "done",
    "fixed", "error", "failed", "using", "into", "over", "only", "also",
    # Sentence-opening verbs / generics that would otherwise leak in as
    # single capitalised "entities" now that bare caps are extracted.
    "added", "removed", "created", "updated", "checked", "reviewed",
    "documented", "tested", "profiled", "deployed", "migrated", "refactored",
    "rolled", "working", "started", "stopped", "switched", "moved", "made",
    "ran", "set", "got", "put", "let", "use", "used", "config", "note",
    "todo", "task", "step", "next", "then", "now", "was", "were", "will",
    "session", "turn", "reply", "answer", "question", "context", "prompt",
    "please", "sure", "okay", "ok", "thanks", "thank", "hello", "hi",
})

# Lowercase infra landmarks that assoc benches + real agent memories use
# constantly — extract_entities otherwise requires Cap/hyphen/snake shape.
_INFRA_ALLOWLIST = frozenset({
    "redis", "postgres", "postgresql", "mysql", "sqlite", "mongodb", "mongo",
    "nginx", "apache", "kubernetes", "k8s", "docker", "podman", "terraform",
    "ansible", "prometheus", "grafana", "elasticsearch", "kafka", "rabbitmq",
    "celery", "fastapi", "django", "flask", "pytorch", "cuda", "ollama",
    "supabase", "cloudflare", "vercel", "github", "gitlab", "s3", "gcs",
    "openai", "anthropic", "hermes", "cuboasis", "cubewave", "engram",
    "neo4j", "clickhouse", "cassandra", "memcached", "traefik", "istio",
    "helm", "pulumi", "nomad", "consul", "vault", "keycloak", "okta",
    "stripe", "twilio", "sendgrid", "datadog", "sentry", "loki", "jaeger",
    "temporal", "airflow", "spark", "flink", "triton", "vllm", "langchain",
    "qdrant", "milvus", "weaviate", "pinecone", "chromadb", "faiss",
    "typescript", "javascript", "python", "golang", "rust", "kotlin",
})

_RE_HASHTAG = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_-]{2,32})\b")
_RE_HANDLE = re.compile(r"(?<!\w)@([A-Za-z][A-Za-z0-9_-]{2,32})\b")
_RE_SEMVER = re.compile(r"^v?\d+(?:\.\d+){1,3}(?:[-+][\w.]+)?$", re.I)

# Known multiword concepts (bee landmarks + Cuboasis pocket dimension)
_CANON_PHRASES = (
    ("mission zero", "Mission Zero"),
    ("founding five", "Founding Five"),
    ("hermes home", "HERMES_HOME"),
    ("memory cube", "memory.cube"),
    ("ship gate", "ship gate"),
    ("query rewrite", "query rewrite"),
    ("cube of eden", "Cube of Eden"),
    ("hermes cube", "HermesCube"),
    ("hermescube", "HermesCube"),
    ("cuboasis", "Cuboasis"),
    ("cubewave", "Cubewave"),
)

# Ownership / relation patterns for stronger entity+edge harvest
_RE_REL_PAIR = re.compile(
    r"\b([A-Z][A-Za-z0-9_.\-]+(?:\s+[A-Z][A-Za-z0-9_.\-]+){0,2})\s+"
    r"(?:owns|uses|runs|manages|prefers|built|wrote|maintains)\s+"
    r"([A-Za-z0-9_.\-/$][A-Za-z0-9_.\-/$]{1,40})",
    re.I,
)
_RE_BACKTICK = re.compile(r"`([A-Za-z0-9_./\-]{2,48})`")
_RE_PATHISH = re.compile(r"(?:^|[\s\"'(])(/[\w./\-]{3,60}|~/[\w./\-]{2,60})")


def _sentence_start_offsets(text: str) -> set[int]:
    """Character offsets where a sentence begins."""
    return {m.end() for m in _RE_SENT_START.finditer(text)}


def extract_entities(text: str, *, max_entities: int = 8) -> list[str]:
    """Entity tokens from one memory description.

    Covers the four shapes that actually carry linkage in agent memories:
    multiword proper nouns ("Alice Nguyen"), machine identifiers
    ("auth-service", "memory.cube", "AuthService"), shell vars
    ("$HERMES_HOME"), and bare proper nouns ("Grafana").

    Bare capitalised words are only taken when they are not sentence-opening
    verbs, since "Deployed the service" must not yield "Deployed".
    """
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()

    def _add(raw: str, *, allow_lower: bool = False) -> None:
        s = " ".join(raw.strip().split())
        if len(s) < 2:
            return
        key = s.lower()
        if key in _STOP_ENT or key in seen:
            return
        if _RE_SEMVER.match(s):
            return
        parts = key.split()
        if len(parts) == 1:
            if len(key) < 4 and key not in _INFRA_ALLOWLIST:
                return
            # single token must look like a name or a machine identifier
            if not (
                allow_lower
                or key in _INFRA_ALLOWLIST
                or s[:1].isupper()
                or s.startswith("$")
                or s.startswith("#")
                or s.startswith("@")
                or "_" in s
                or "." in s
                or "-" in s
            ):
                return
        seen.add(key)
        found.append(s)

    low = text.lower()
    # Seed infra allowlist when the token appears as a whole word
    for tok in _INFRA_ALLOWLIST:
        if re.search(rf"(?<![a-z0-9_]){re.escape(tok)}(?![a-z0-9_])", low):
            _add(tok, allow_lower=True)
    for m in _RE_HASHTAG.finditer(text):
        _add("#" + m.group(1), allow_lower=True)
    for m in _RE_HANDLE.finditer(text):
        _add("@" + m.group(1), allow_lower=True)
    for phrase, label in _CANON_PHRASES:
        if phrase in low or phrase.replace(" ", "_") in low:
            _add(label)

    for m in _RE_EQUALS_NAME.finditer(text):
        _add(m.group(1))
    for m in _RE_MULTI_CAP.finditer(text):
        _add(m.group(1))
    for m in _RE_DOLLAR.finditer(text):
        _add(m.group(0).split("/")[0])  # $HERMES_HOME from longer path
    for m in _RE_QUOTE.finditer(text):
        _add(m.group(1))
    for m in _RE_BACKTICK.finditer(text):
        _add(m.group(1))
    for m in _RE_REL_PAIR.finditer(text):
        _add(m.group(1))
        _add(m.group(2), allow_lower=True)
    for m in _RE_PATHISH.finditer(text):
        # Keep basename-ish path tokens without flooding with full trees
        p = m.group(1).rstrip(".,;:)")
        base = p.rsplit("/", 1)[-1]
        if base and len(base) >= 3:
            _add(base)
        if len(p) <= 40:
            _add(p)

    # Machine identifiers — dotted before hyphen/snake so "memory.cube" is
    # captured whole rather than as two fragments.
    for rx in (_RE_DOTTED_ID, _RE_HYPHEN_ID, _RE_SNAKE_ID, _RE_CAMEL):
        for m in rx.finditer(text):
            _add(m.group(0))

    # Bare proper nouns, minus sentence-opening inflected verbs.
    starts = _sentence_start_offsets(text)
    for m in _RE_CAP_TOKEN.finditer(text):
        tok = m.group(0)
        if tok.lower() in seen:
            continue
        if m.start() in starts:
            low_tok = tok.lower()
            if low_tok.endswith(_VERBISH_SUFFIX) or low_tok in _STOP_ENT:
                continue
        _add(tok)

    # bio tokens
    for tok in bio_rank.tokenize(text):
        if tok in ("hermes_home", "memory_cube", "mission_zero", "founding_five"):
            _add(tok)

    return _drop_fragments(found)[:max_entities]


def _drop_fragments(found: list[str]) -> list[str]:
    """Remove single words that are already part of an accepted phrase.

    "Alice Nguyen" should be one node, not three ("Alice Nguyen", "Alice",
    "Nguyen") — fragments would fan out the trail graph into noise.
    """
    phrases = [f for f in found if " " in f]
    if not phrases:
        return found
    covered: set[str] = set()
    for p in phrases:
        for word in p.lower().split():
            covered.add(word)
    return [f for f in found if " " in f or f.lower() not in covered]


def norm_key(entity: str) -> str:
    """Canonical graph key: "auth-service", "auth_service" and "auth service"
    are the same node."""
    return " ".join(str(entity or "").lower().replace("-", " ").replace("_", " ").split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


_RE_WORD = re.compile(r"[a-z][a-z0-9]{3,}")
# A term seen in more than this share of the archive is background vocabulary
# ("service", "the batch"), not a landmark worth linking on.
_MINE_MAX_DF_RATIO = 0.25
_MINE_MIN_DF_TERM = 3
_MINE_MIN_DF_PHRASE = 2


def mine_corpus_terms(
    descriptions: list[str],
) -> tuple[set[str], set[str]]:
    """Find lowercase terms and phrases that recur across the archive.

    Plain words like "redis" or "postgres" are real entities but are
    indistinguishable from ordinary vocabulary in a single sentence. Across
    the whole archive they separate cleanly: a landmark recurs in a handful
    of memories, while filler recurs in nearly all of them. This is the same
    logic as IDF, used here to decide what deserves a node in the graph.

    Returns (terms, phrases) already filtered by document frequency.
    """
    n = len(descriptions)
    if n < 2:
        return set(), set()
    term_df: dict[str, int] = defaultdict(int)
    phrase_df: dict[str, int] = defaultdict(int)
    for desc in descriptions:
        words = _RE_WORD.findall((desc or "").lower())
        keep = [w for w in words if w not in _STOP_ENT and w not in bio_rank._STOP]
        for w in set(keep):
            term_df[w] += 1
        seen_ph: set[str] = set()
        for a, b in zip(keep, keep[1:]):
            seen_ph.add(f"{a} {b}")
        for ph in seen_ph:
            phrase_df[ph] += 1

    # Small corpora of near-duplicate seeds would otherwise treat every
    # recurring landmark as "background" (df ≈ n). Allow full df there.
    if n < 20:
        max_df = n
    else:
        max_df = max(_MINE_MIN_DF_TERM, int(n * _MINE_MAX_DF_RATIO))
    terms = {
        w for w, df in term_df.items()
        if _MINE_MIN_DF_TERM <= df <= max_df
    }
    phrases = {
        p for p, df in phrase_df.items()
        if _MINE_MIN_DF_PHRASE <= df <= max_df
    }
    # A phrase supersedes its own words as a node.
    for p in phrases:
        for w in p.split():
            terms.discard(w)
    return terms, phrases


def build_entity_index(
    entries: Iterable[Any], *, mine: bool = True
) -> dict[str, list[Any]]:
    """entity_lower → list of entries mentioning it.

    Combines per-description extraction with archive-level term mining so
    that plain-word entities participate in the graph too.
    """
    entries = list(entries)
    mined_terms: set[str] = set()
    mined_phrases: set[str] = set()
    if mine:
        mined_terms, mined_phrases = mine_corpus_terms(
            [getattr(e, "description", "") or "" for e in entries]
        )

    idx: dict[str, list[Any]] = defaultdict(list)
    for e in entries:
        desc = getattr(e, "description", "") or ""
        ents = extract_entities(desc)
        data = getattr(e, "data", None) or {}
        if isinstance(data, dict):
            extra = data.get("entities") or []
            if isinstance(extra, list):
                # re-filter stored entities through hygiene
                for x in extra:
                    for cleaned in extract_entities(str(x)):
                        if cleaned not in ents:
                            ents.append(cleaned)
        if mined_terms or mined_phrases:
            low = desc.lower()
            for ph in mined_phrases:
                if ph in low:
                    ents.append(ph)
            words = set(_RE_WORD.findall(low))
            for w in words & mined_terms:
                ents.append(w)

        # Collapse variants ("auth-service" / "auth service") to one node and
        # keep the first spelling seen as the display form.
        deduped: list[str] = []
        keys: set[str] = set()
        for ent in ents:
            k = norm_key(ent)
            if not k or k in keys:
                continue
            keys.add(k)
            deduped.append(ent)
        ents = deduped

        for ent in ents:
            idx[norm_key(ent)].append(e)
        try:
            if isinstance(data, dict):
                data = dict(data)
                data["entities"] = ents
                e.data = data  # type: ignore[attr-defined]
        except Exception:
            pass
    return idx


def entry_id(e: Any) -> str:
    return str(getattr(e, "id", "") or id(e))


def mirror_expand(
    seeds: list[tuple[Any, float]],
    all_entries: list[Any],
    *,
    top_k: int = 5,
    entity_index: dict[str, list[Any]] | None = None,
    colony: Any = None,
) -> list[tuple[Any, float]]:
    """Primary hits + co-entity / parent / trail-boosted neighbors."""
    if not seeds:
        return []
    if entity_index is None:
        entity_index = build_entity_index(all_entries)

    by_id = {entry_id(e): e for e in all_entries}
    picked: list[tuple[Any, float]] = []
    seen: set[str] = set()

    def _ents(e: Any) -> list[str]:
        data = getattr(e, "data", None) or {}
        if isinstance(data, dict) and data.get("entities"):
            return [str(x) for x in data["entities"]]
        return extract_entities(getattr(e, "description", "") or "")

    def _take(e: Any, score: float) -> None:
        eid = entry_id(e)
        if not eid or eid in seen:
            return
        seen.add(eid)
        picked.append((e, score))

    for e, sc in seeds:
        _take(e, sc)
        if len(picked) >= top_k:
            return picked[:top_k]

    # Score every reachable neighbour, then take the best — picking in index
    # order would return an arbitrary member of whichever node was hit first.
    candidates: dict[str, tuple[Any, float]] = {}

    def _offer(node: Any, score: float) -> None:
        """Accumulate evidence: a neighbour linked through several shared
        entities is a stronger match than one linked through a single entity,
        so paths add (with diminishing returns) rather than taking the max."""
        nid = entry_id(node)
        if not nid or nid in seen:
            return
        prev = candidates.get(nid)
        if prev is None:
            candidates[nid] = (node, score)
        else:
            candidates[nid] = (prev[0], prev[1] + score * 0.5)

    for e, sc in list(seeds):
        ents = _ents(e)
        for ent in ents:
            key = norm_key(ent)
            bucket = entity_index.get(key, [])
            if not bucket:
                continue
            # A shared entity that only a few memories mention is far stronger
            # evidence of a real link than one half the archive mentions.
            specificity = 1.0 / math.log(2.0 + len(bucket))
            for neigh in bucket:
                echo = float(sc) * 0.72 * specificity
                if colony is not None:
                    try:
                        echo *= float(colony.trail_boost(ents, _ents(neigh)))
                    except Exception:
                        pass
                _offer(neigh, echo)
        for pid in getattr(e, "causal_parents", None) or []:
            parent = by_id.get(str(pid))
            if parent is not None:
                _offer(parent, float(sc) * 0.8)

    # Ties break on content, not entry id: two archives holding the same
    # memories should rank them the same way regardless of the ids assigned
    # when they happened to be written.
    for node, score in sorted(
        candidates.values(),
        key=lambda x: (-x[1], getattr(x[0], "description", "") or "", entry_id(x[0])),
    ):
        _take(node, score)
        if len(picked) >= top_k:
            break

    return picked[:top_k]


def annotate_entities_on_append(description: str, data: dict | None) -> dict:
    """Attach cleaned entities list into entry data at write time."""
    d = dict(data or {})
    ents = extract_entities(description)
    if ents:
        d["entities"] = ents
    elif "entities" in d:
        # re-clean legacy
        d["entities"] = extract_entities(" ".join(str(x) for x in d.get("entities") or []))
    return d


def enrich_entries_with_mined_entities(
    cube: Any,
    entries: list[Any] | None = None,
    *,
    max_touch: int = 12,
) -> dict[str, Any]:
    """Persist corpus-mined lowercase landmarks as ``[ENTITY]`` rows.

    Append-only: one landmark row per mined term (idempotent). HAR entity
    overlap then sees stable nodes without rewriting history. Skips terms
    already present on any entry's ``data.entities`` *and* already mined.
    """
    if cube is None:
        return {"ok": False, "enriched": 0}
    try:
        ents = list(entries) if entries is not None else list(cube.read_l1() or [])
    except Exception:
        return {"ok": False, "enriched": 0, "error": "read_l1 failed"}
    if len(ents) < 4:
        return {"ok": True, "enriched": 0, "skipped": "too_few"}

    # Do not mine from prior [ENTITY] rows — that creates an endless feedback loop
    descs = [
        getattr(e, "description", "") or ""
        for e in ents
        if not (getattr(e, "description", "") or "").startswith("[ENTITY]")
    ]
    terms, phrases = mine_corpus_terms(descs)
    landmarks = set(terms) | set(phrases)
    if not landmarks:
        return {"ok": True, "enriched": 0, "skipped": "no_mined"}

    existing_entity_rows = {
        (e.description or "").lower()
        for e in ents
        if (e.description or "").startswith("[ENTITY]")
    }
    already_on_entries: set[str] = set()
    for e in ents:
        data = e.data if isinstance(getattr(e, "data", None), dict) else {}
        for x in data.get("entities") or []:
            already_on_entries.add(str(x).lower())

    touched = 0
    samples: list[str] = []
    # Prefer terms that actually appear in recent descriptions
    for term in sorted(landmarks, key=len, reverse=True):
        if touched >= max_touch:
            break
        label = f"[ENTITY] {term}"
        if label.lower() in existing_entity_rows:
            continue
        # Need at least one supporting description
        if not any(term in (d or "").lower() for d in descs):
            continue
        try:
            cube.append(
                entry_type="landmark",
                description=label,
                data={
                    "source": "entity_mine",
                    "durable": True,
                    "trust": 0.55,
                    "entities": [term],
                    "mined": True,
                },
                outcome="none",
            )
            existing_entity_rows.add(label.lower())
            touched += 1
            if len(samples) < 5:
                samples.append(term)
        except Exception:
            continue
    return {
        "ok": True,
        "enriched": touched,
        "mined_terms": len(terms),
        "mined_phrases": len(phrases),
        "already_labeled": len(already_on_entries),
        "samples": samples,
    }
