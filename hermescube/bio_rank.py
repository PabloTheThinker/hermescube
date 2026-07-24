"""Bio-inspired ranking and consolidation helpers for HermesCube.

Maps comparative cognition → operational memory policy:

| Species / system | Mechanism | Cube mapping |
|------------------|-----------|--------------|
| Human hippocampus | encode / consolidate / index | L1 append + evolve L2 |
| Human PFC | working / executive control | prefetch top-k budget + FOA |
| Human neocortex | long-term schema | L2 topics + skills (culture) |
| Elephant | long spatial/social maps | slow decay on landmark/relationship |
| Dolphin | auditory + cross-modal + USWS | type routing + unihemispheric offline |
| Whale | culture + migratory maps | evolution/resolve durable; landmarks |

Hot path stays cheap (Quicksilver). Sleep/consolidation is offline only.
"""

from __future__ import annotations

import math
import re
from typing import Any

# Cortical layers (cognitive-web hierarchy → entry types)
# sensory → associative → executive → meta
LAYER_OF_TYPE: dict[str, str] = {
    "enter": "sensory",
    "leave": "sensory",
    "landmark": "associative",  # elephant routes / places / events
    "belief": "associative",
    "trait": "associative",  # durable prefs
    "relationship": "associative",  # elephant social graph
    "focus": "executive",
    "resolve": "executive",
    "evolution": "meta",
    "epoch_transition": "meta",
}

# Half-life in hours for recency decay (longer = elephant-like retention)
# score *= exp(-delta_hours / half_life)
HALF_LIFE_HOURS: dict[str, float] = {
    "trait": 720.0,  # ~30d — identity-stable
    "relationship": 2160.0,  # ~90d — social recognition
    "landmark": 1440.0,  # ~60d — spatial / route memory
    "belief": 336.0,  # ~14d
    "resolve": 504.0,  # ~21d decisions
    "evolution": 720.0,
    "focus": 48.0,  # working / FOA
    "enter": 24.0,
    "leave": 24.0,
    "epoch_transition": 720.0,
}
DEFAULT_HALF_LIFE_HOURS = 48.0

# Layer mix targets for hierarchical prefetch (not pure similarity dump)
LAYER_QUOTA: dict[str, int] = {
    "executive": 2,
    "associative": 5,
    "meta": 1,
    "sensory": 1,
}

# Outcome multipliers
OUTCOME_WEIGHT: dict[str, float] = {
    "success": 1.08,
    "failure": 1.05,  # failures are high value (lessons)
    "pending": 0.95,
    "superseded": 0.35,
    "none": 1.0,
}

# Cheap IR: expand query stems without LLM (paraphrase bridge)
_SYN_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"bug", "bugs", "fixed", "fix", "hotfix", "patch", "debug", "debugged"}),
    frozenset({"prefer", "prefers", "preference", "preferences", "habit", "habits", "like", "likes", "style"}),
    frozenset({"auth", "authentication", "login", "security", "secure", "password", "oauth"}),
    frozenset({"deploy", "deployed", "deployment", "production", "prod", "release", "shipped"}),
    frozenset({"decide", "decided", "decision", "decisions", "chose", "choice", "conclusion"}),
    frozenset({"performance", "perf", "latency", "slow", "optimize", "optimized", "profiling"}),
    frozenset({"priority", "prioritizing", "attention", "focus", "sprint", "urgent", "needs"}),
    frozenset({"complete", "completed", "done", "finished", "resolved", "shipped"}),
    frozenset({"evolved", "evolution", "changed", "architecture", "migrated", "refactored"}),
    frozenset({"database", "db", "storage", "schema", "sql", "persist"}),
    frozenset({"monitor", "monitoring", "alert", "alerts", "logging", "logs"}),
    frozenset({"lesson", "lessons", "learned", "learning", "insight"}),
    frozenset({"user", "client", "customer"}),
    frozenset({"memory", "recall", "remember", "cube", "har"}),
)

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
_STOP = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "for", "and", "or", "but", "with", "as", "at",
    "by", "from", "that", "this", "it", "its", "we", "you", "they", "i",
    "me", "my", "our", "your", "what", "who", "how", "when", "where", "why",
    "do", "does", "did", "can", "could", "should", "would", "will", "just",
    "about", "into", "over", "after", "before", "than", "then", "also",
})


def _stem(tok: str) -> str:
    t = tok.lower()
    for sfx in ("ing", "tion", "ness", "ment", "ies", "ied", "ed", "es", "s"):
        if len(t) > len(sfx) + 2 and t.endswith(sfx):
            return t[: -len(sfx)]
    return t


def tokenize(text: str) -> set[str]:
    raw = _TOKEN_RE.findall(text or "")
    out: set[str] = set()
    for t in raw:
        tl = t.lower()
        if len(tl) < 2 or tl in _STOP:
            continue
        # drop pure numbers / dates noise
        if tl.isdigit():
            continue
        out.add(tl)
        out.add(_stem(t))
    # synonym closure
    expanded = set(out)
    for g in _SYN_GROUPS:
        if out & g:
            expanded |= g
            expanded |= {_stem(x) for x in g}
    return expanded


def lexical_score(query: str, document: str) -> float:
    """Jaccard-ish overlap after stem+synonym expand. Range ~[0,1]."""
    q = tokenize(query)
    d = tokenize(document)
    if not q or not d:
        return 0.0
    inter = len(q & d)
    if inter == 0:
        return 0.0
    # asymmetric: how much of the query is covered
    cover = inter / max(len(q), 1)
    jacc = inter / max(len(q | d), 1)
    return min(1.0, 0.65 * cover + 0.35 * jacc)


def hybrid_semantic(semantic: float, lexical: float, *, lex_weight: float = 0.55) -> float:
    """Blend HRR cosine with lexical bridge. Lexical dominates misses on hash embeds."""
    s = max(0.0, float(semantic))
    lx = max(0.0, min(1.0, float(lexical)))
    w = max(0.0, min(1.0, lex_weight))
    # when lexical is strong, lift weak semantic (paraphrase rescue)
    base = (1.0 - w) * s + w * lx
    if lx >= 0.25 and s < 0.15:
        base = max(base, 0.45 * lx + 0.2)
    return base


def cortical_layer(entry_type: str) -> str:
    return LAYER_OF_TYPE.get(entry_type or "", "associative")


def half_life_hours(entry_type: str) -> float:
    return float(HALF_LIFE_HOURS.get(entry_type or "", DEFAULT_HALF_LIFE_HOURS))


def type_prior(entry_type: str) -> float:
    """Mild boost for durable social/spatial types (elephant prior)."""
    return {
        "trait": 1.12,
        "relationship": 1.15,
        "landmark": 1.10,
        "resolve": 1.08,
        "belief": 1.05,
        "evolution": 1.04,
        "focus": 1.18,  # open prospective intents stay hot
        "enter": 0.9,
        "leave": 0.9,
        "epoch_transition": 1.02,
    }.get(entry_type or "", 1.0)


def trust_multiplier(trust: float | None) -> float:
    """Map trust in [0,1] → [0.55, 1.25]. Neutral 0.5 → 1.0."""
    if trust is None:
        return 1.0
    try:
        t = float(trust)
    except (TypeError, ValueError):
        return 1.0
    t = max(0.0, min(1.0, t))
    return 0.55 + (t * 0.70)


def outcome_multiplier(outcome: str) -> float:
    return float(OUTCOME_WEIGHT.get(outcome or "none", 1.0))


def recency_weight(delta_hours: float, entry_type: str) -> float:
    """Type-aware exponential decay (adaptive consolidation / forgetting)."""
    hl = half_life_hours(entry_type)
    if hl <= 1e-6:
        return 1.0
    d = max(0.0, float(delta_hours))
    return math.exp(-d / hl)


def source_boost(data: dict | None) -> float:
    """Durable channels (manage/seed) outrank ephemeral turns."""
    if not data or not isinstance(data, dict):
        return 1.0
    if data.get("prospective_closed") is True:
        return 0.9
    if data.get("crystal") is True:
        return 1.55  # active wisdom — consensus crystals
    src = str(data.get("source") or data.get("indexed_from") or "").lower()
    if src in ("seed", "manage", "user", "import", "cli", "hermescube_manage", "extract", "wisdom_crystalizer"):
        return 1.35
    if src in ("assistant", "turn", "sync_turn"):
        return 0.85
    if data.get("durable") is True:
        return 1.35
    if data.get("question"):
        return 0.80
    return 1.0


def extract_fact_lines(assistant: str, *, max_facts: int = 3) -> list[tuple[str, str]]:
    """Regex fact lines from assistant text — no LLM.

    Returns list of (entry_type, description).
    """
    if not assistant:
        return []
    lines = []
    text = assistant.strip()
    # "Name = role" / "X is Y" short definitions
    for m in re.finditer(
        r"(?m)^[\s\-\*]*([A-Z][\w .'-]{1,40})\s*=\s*([^\n.]{3,80})",
        text,
    ):
        lines.append(("relationship", f"{m.group(1).strip()} = {m.group(2).strip()}"))
    for m in re.finditer(
        r"(?i)\b(?:user |they |he |she )?(?:prefer(?:s)?|likes?|wants?)\s+([^\n.]{3,60})",
        text,
    ):
        lines.append(("trait", f"Prefers {m.group(1).strip()}"))
    for m in re.finditer(
        r"(?i)\b(?:path|lives? at|stored at|file)\s*[:=]?\s*(\$[\w{/}./-]+|~/?[\w./-]+|/[\w./-]+)",
        text,
    ):
        lines.append(("landmark", f"Path: {m.group(1).strip()}"))
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for et, d in lines:
        key = d.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((et, d[:200]))
        if len(out) >= max_facts:
            break
    return out


def composite_score(
    semantic: float,
    *,
    entry_type: str,
    outcome: str = "none",
    trust: float | None = None,
    delta_hours: float = 0.0,
    lexical: float = 0.0,
    description: str = "",
    data: dict | None = None,
    yield_boost: float = 1.0,
) -> float:
    """Combine hybrid similarity with bio priors for ranking.

    yield_boost: query-conditioned payoff multiplier from YieldGradient
    (closed learning loop — what paid off for *similar queries*).
    """
    sim = hybrid_semantic(semantic, lexical)
    r = recency_weight(delta_hours, entry_type)
    yb = float(yield_boost) if yield_boost and yield_boost > 0 else 1.0
    # keep yield influence bounded
    yb = max(0.75, min(1.40, yb))
    score = (
        float(sim)
        * r
        * type_prior(entry_type)
        * trust_multiplier(trust)
        * outcome_multiplier(outcome)
        * source_boost(data)
        * yb
    )
    # Downrank raw question-shaped surfaces (legacy turn noise)
    d = (description or "").strip()
    if d.endswith("?") or d[:4].lower() in ("who ", "what", "wher", "when", "why ", "how "):
        score *= 0.55
    return score


def diversify_by_layer(
    scored: list[tuple[Any, float]],
    top_k: int,
    entry_type_fn=None,
) -> list[tuple[Any, float]]:
    """Everyday IR: trust score order first.

    Only soft-inject one missing executive/meta item if its score is within
    60% of the leader — never shove low-relevance “layer fillers” above gold.
    """
    if top_k <= 0 or not scored:
        return []
    if entry_type_fn is None:
        entry_type_fn = lambda e: getattr(e, "entry_type", "")  # noqa: E731

    # Primary: pure rank (hybrid score already applied)
    head = list(scored[:top_k])
    if len(scored) <= top_k:
        return head

    top_score = float(scored[0][1]) if scored else 0.0
    if top_score <= 0:
        return head

    present = {cortical_layer(str(entry_type_fn(e))) for e, _ in head}
    used = {id(e) for e, _ in head}
    # Soft fill only if a strong-ish candidate exists outside head
    for want in ("executive", "meta"):
        if want in present or len(head) >= top_k:
            continue
        for entry, score in scored[top_k: top_k + 40]:
            if id(entry) in used:
                continue
            if cortical_layer(str(entry_type_fn(entry))) != want:
                continue
            if float(score) < 0.60 * top_score:
                break
            # replace weakest head item if weaker
            head.sort(key=lambda x: -x[1])
            if float(score) > float(head[-1][1]):
                head[-1] = (entry, score)
                used.add(id(entry))
                present.add(want)
            break
    head.sort(key=lambda x: -x[1])
    return head[:top_k]


def meta_memory_report(entries: list[Any], topics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Self-reflective / meta-memory snapshot for system prompt & tools."""
    type_counts: dict[str, int] = {}
    layer_counts: dict[str, int] = {}
    trust_vals: list[float] = []
    superseded = 0
    for e in entries:
        et = getattr(e, "entry_type", "") or "unknown"
        type_counts[et] = type_counts.get(et, 0) + 1
        layer = cortical_layer(et)
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
        data = getattr(e, "data", None) or {}
        if isinstance(data, dict) and "trust" in data:
            try:
                trust_vals.append(float(data["trust"]))
            except (TypeError, ValueError):
                pass
        if getattr(e, "outcome", "") == "superseded":
            superseded += 1

    hubs = []
    if topics:
        hubs = sorted(topics, key=lambda t: -float(t.get("quality", 0)))[:5]
        hubs = [
            {
                "terms": (t.get("terms") or [])[:4],
                "quality": t.get("quality"),
                "entries": t.get("entries"),
            }
            for t in hubs
        ]

    return {
        "entry_count": len(entries),
        "by_type": type_counts,
        "by_layer": layer_counts,
        "mean_trust": round(sum(trust_vals) / len(trust_vals), 3) if trust_vals else None,
        "superseded": superseded,
        "hubs": hubs,
        "policy": {
            "hot_path": "query/prefetch (awake hemisphere)",
            "sleep_path": "evolve_consolidated / session_end (offline hemisphere)",
            "rewrite_default": False,
        },
    }
