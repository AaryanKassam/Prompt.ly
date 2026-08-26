"""Outcome-signal extraction from session sequences.

These measure *what happened after* a prompt — whether the user had to repeat
themselves, how many follow-ups a task needed, whether Claude asked for
clarification, and how well the resulting file changes matched the prompt.

Phase 5 turns these into weak training labels. For now they power an
``outcome_score`` used for analytics. Implementations use token-overlap
(Jaccard) as a cheap stand-in for the semantic cosine similarity the handoff
describes; they'll be upgraded to embeddings when sentence-transformers lands.
"""
from __future__ import annotations

import re

_CLARIFY_PATTERNS = [
    r"\bcould you clarify\b", r"\bcan you clarify\b", r"\bwhich \w+ do you\b",
    r"\bdo you want\b", r"\bwhat do you mean\b", r"\bto confirm\b",
    r"\ba few questions\b", r"\bcan you confirm\b", r"\bshould i\b.*\?",
]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def detect_repetition(prompt_text: str, next_prompt_text: str) -> float:
    """Similarity of consecutive prompts. High => the user repeated themselves."""
    return round(_jaccard(prompt_text, next_prompt_text), 3)


def detect_iteration_count(prompts: list, index: int, threshold: float = 0.35) -> int:
    """How many following turns stay on the same topic as ``prompts[index]``.

    ``prompts`` is an ordered list of objects/dicts with a ``.text``/['text'].
    Consecutive similar turns imply the task needed several tries to land.
    """
    def _text(p) -> str:
        return getattr(p, "text", None) if not isinstance(p, dict) else p.get("text")

    base = _text(prompts[index]) or ""
    count = 0
    for nxt in prompts[index + 1 :]:
        if _jaccard(base, _text(nxt) or "") >= threshold:
            count += 1
        else:
            break
    return count


def detect_clarification_request(claude_response_text: str) -> bool:
    """Did Claude ask a clarifying question before acting?"""
    low = (claude_response_text or "").lower()
    return any(re.search(p, low) for p in _CLARIFY_PATTERNS)


def compute_diff_alignment(prompt_text: str, file_diffs: dict | None) -> float:
    """Overlap between the prompt's intent and the files that changed."""
    if not file_diffs:
        return 0.0
    paths = []
    for key in ("created", "edited", "deleted"):
        paths.extend(file_diffs.get(key, []) or [])
    if not paths:
        return 0.0
    # Compare prompt tokens against filename stems (e.g. "auth" in auth_router.py).
    stems = " ".join(re.sub(r"[\W_]+", " ", p.rsplit("/", 1)[-1]) for p in paths)
    return round(_jaccard(prompt_text, stems), 3)


def compute_outcome_score(
    prompt_text: str,
    next_prompt_text: str,
    response_text: str,
    file_diffs: dict | None,
    iteration_count: int,
) -> float:
    """Composite 0-10 outcome label (higher = the prompt worked well)."""
    score = 10.0
    score -= 3.0 * detect_repetition(prompt_text, next_prompt_text)      # -0..3
    score -= min(2.0, 0.5 * iteration_count)                            # -0..2
    score -= 1.0 if detect_clarification_request(response_text) else 0.0  # -0..1
    score += compute_diff_alignment(prompt_text, file_diffs)            # +0..1
    return round(max(0.0, min(10.0, score)), 2)
