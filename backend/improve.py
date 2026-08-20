"""Explain what's weak about a prompt and draft a stronger version of it.

Deliberately rule-based, like the scorer. Nothing here calls a language model,
so the "improved" prompt is never invented text — it is the user's own words
rearranged into a structure that satisfies the signals they missed, with
bracketed slots for the information only they can supply.

That honesty matters: a generated rewrite that silently invents a file path or
a rationale would be worse than useless, because it would look authoritative
while being fiction.
"""
from __future__ import annotations

import re

from .ingestion.classify import clean
from .ml.features import extract_signals

# Human-readable name + why it costs you, per signal.
ISSUES: dict[str, tuple[str, str]] = {
    "clarity.single_imperative_verb": ("No clear action verb", "The model has to guess whether you're asking, reporting, or thinking aloud."),
    "clarity.no_passive_voice": ("Passive voice", "Hides who should do what, so the change can land in the wrong place."),
    "clarity.no_hedge_words": ("Hedging", "\"Maybe\" and \"I think\" invite the model to hedge back instead of committing."),
    "clarity.sentence_count_le_5": ("Too long", "The actual ask is buried; earlier sentences crowd out later ones."),
    "specificity.mentions_file_or_line": ("No file named", "Costs a search, and the search can land on the wrong file."),
    "specificity.names_exact_function_class": ("No exact identifiers", "Describing a function instead of naming it invites the wrong one."),
    "specificity.has_concrete_output_format": ("No output shape", "You get prose when you wanted a diff, or a diff when you wanted prose."),
    "specificity.no_vague_quantifiers": ("Vague quantifiers", "\"Better\" and \"some\" have no finish line, so nothing can be checked off."),
    "context.references_prior_turn": ("Unanchored follow-up", "Context gets rebuilt from scratch, often wrongly."),
    "context.provides_background_why": ("No rationale", "Without intent the model can't make the judgment calls you'd make."),
    "context.mentions_tech_stack": ("Stack unstated", "Invites idiomatic answers for the wrong framework or version."),
    "constraints.has_negative_constraint": ("No guardrails", "Nothing prevents collateral edits you'll have to undo."),
    "constraints.specifies_scope_limit": ("Unbounded scope", "The blast radius is whatever the model decides it is."),
    "scope.single_task_focus": ("Multiple tasks", "Bundled asks get uneven attention and are harder to review."),
    "scope.no_compound_and_also": ("Compound request", "The second half of an \"and also\" reliably gets less effort."),
    "scope.task_size_appropriate": ("Oversized", "Past ~200 words a prompt usually hides two or three separate jobs."),
    "examples.has_code_block": ("No code or error pasted", "Paraphrased errors lose the detail that identifies the cause."),
    "examples.has_before_after": ("No before/after", "Current-vs-desired is the fastest way to convey a behaviour change."),
    "examples.has_inline_example": ("No example", "One concrete case removes more ambiguity than a paragraph of description."),
}

_HEDGES = re.compile(
    r"\b(maybe|perhaps|i think|i guess|possibly|probably|sort of|kind of|"
    r"if you can|if possible|just|somewhat|or something)\b[,]?\s*",
    re.IGNORECASE,
)
_FILLER_OPENERS = re.compile(
    r"^(hey|hi|ok|okay|so|well|also|and|but|can you|could you|please|"
    r"i want you to|i need you to|i was wondering if you could|would you)\b[,]?\s*",
    re.IGNORECASE,
)
_FILE_RE = re.compile(r"\b[\w\-./]+\.(py|js|ts|tsx|jsx|json|md|css|html|sql|ya?ml|toml)\b")
_IDENT_RE = re.compile(r"`([^`]+)`")

_IMPERATIVES = {
    "add", "create", "build", "write", "implement", "fix", "refactor", "remove",
    "delete", "update", "change", "rename", "move", "extract", "replace", "make",
    "generate", "parse", "convert", "optimize", "test", "document", "wire", "extend",
    "install", "configure", "set", "run", "split", "merge", "validate", "handle",
    "explain", "show", "check", "review", "audit", "support", "expose",
    # Version control, ops and data verbs the first pass missed.
    "push", "commit", "pull", "clone", "rebase", "revert", "tag", "deploy",
    "release", "publish", "start", "stop", "restart", "open", "close", "connect",
    "sync", "scan", "score", "track", "list", "find", "search", "load", "save",
    "export", "import", "upgrade", "downgrade", "migrate", "format", "lint",
    "clean", "enable", "disable", "print", "log", "cache", "filter", "sort",
    "rewrite", "port", "bump", "pin", "mock", "stub", "benchmark", "profile",
}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def find_issues(text: str) -> list[dict]:
    """Every signal the prompt misses, worst-weighted factors first."""
    signals = extract_signals(text)
    order = ["clarity", "specificity", "context", "constraints", "scope", "examples"]
    issues = []
    for factor in order:
        for name, hit in signals.get(factor, {}).items():
            key = f"{factor}.{name}"
            if hit or key not in ISSUES:
                continue
            label, why = ISSUES[key]
            issues.append({"signal": key, "factor": factor, "label": label, "why": why})
    return issues


def _core_ask(text: str) -> str:
    """The user's request, de-hedged and pointed at an action."""
    sentences = _sentences(text)
    if not sentences:
        return "[state the single thing you want done]"

    core = _FILLER_OPENERS.sub("", _HEDGES.sub("", sentences[0])).strip(" ,;")
    if not core:
        return "[state the single thing you want done]"

    first = core.split()[0].lower().strip(",.")
    if first not in _IMPERATIVES:
        # Not imperative — flag rather than fabricate a verb we can't infer.
        core = f"[action verb] {core}"
    return core[0].upper() + core[1:] if core else core


def rewrite(text: str) -> dict:
    """Build a stronger version of the prompt.

    Sections are only added for signals the original actually misses, so a
    prompt that already explains itself doesn't get a redundant "Why:" line.
    Bracketed slots mark information the user must supply — they are never
    filled with guesses.
    """
    cleaned = clean(text)
    signals = extract_signals(cleaned)
    sentences = _sentences(cleaned)

    lines: list[str] = [_core_ask(cleaned)]

    # Preserve any detail the user already gave, minus the opening sentence.
    detail = " ".join(sentences[1:]).strip()
    if detail and len(detail) < 400:
        lines.append("")
        lines.append(_HEDGES.sub("", detail).strip())

    additions: list[str] = []
    spec, ctx, con, ex = (
        signals["specificity"], signals["context"], signals["constraints"], signals["examples"]
    )

    if not spec["mentions_file_or_line"]:
        found = _FILE_RE.findall(cleaned)
        additions.append(
            f"Files: `{found[0]}`" if found else "Files: `[path/to/the/file.py]`"
        )
    if not ctx["provides_background_why"]:
        additions.append("Why: [what this unblocks, or what breaks without it]")
    if not spec["has_concrete_output_format"]:
        additions.append("Output: [a diff / a function signature / JSON with keys x, y]")
    if not (con["has_negative_constraint"] or con["specifies_scope_limit"]):
        additions.append("Constraints: [what not to touch — files, deps, behaviour]")
    if not (ex["has_code_block"] or ex["has_inline_example"] or ex["has_before_after"]):
        additions.append("Example: [concrete input → the output you expect]")

    if additions:
        lines.append("")
        lines.extend(additions)

    return {
        "rewrite": "\n".join(lines),
        "slots": sum(1 for a in additions if "[" in a),
        "kept_detail": bool(detail),
    }


def improve(text: str) -> dict:
    """Full improvement payload: what's wrong, and a stronger draft."""
    cleaned = clean(text)
    issues = find_issues(cleaned)
    return {
        "original": cleaned,
        "issues": issues,
        "issue_count": len(issues),
        **rewrite(cleaned),
    }
