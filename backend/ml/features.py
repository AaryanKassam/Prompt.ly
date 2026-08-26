"""Structural feature extraction for the Phase 1 rubric scorer.

Each function is a rule-based heuristic returning a bool for one rubric *signal*.
They are pure text heuristics (no ML dependencies) so scoring is instant and runs
at ingestion time. Phase 2's MLP will consume these same signals as a feature
vector alongside embeddings.
"""
from __future__ import annotations

import re

# --- lexicons -------------------------------------------------------------

# Common imperative verbs that open a well-formed coding instruction.
_IMPERATIVE_VERBS = {
    "add", "create", "build", "write", "implement", "fix", "refactor", "remove",
    "delete", "update", "change", "rename", "move", "extract", "replace", "make",
    "generate", "parse", "convert", "optimize", "test", "document", "wire", "extend",
    "install", "configure", "set", "run", "split", "merge", "validate", "handle",
}

_HEDGE_WORDS = {
    "maybe", "perhaps", "kind of", "sort of", "somewhat", "i think", "i guess",
    "possibly", "probably", "might", "could be", "not sure", "or something",
}

_VAGUE_QUANTIFIERS = {
    "some", "a few", "several", "many", "a bit", "a little", "better", "nicer",
    "cleaner", "improve", "stuff", "things", "etc",
}

_NEGATIVE_CONSTRAINTS = {
    "don't", "do not", "avoid", "without", "never", "no ", "not ", "except",
    "instead of", "rather than",
}

_SCOPE_LIMIT_PHRASES = {
    "only", "just", "leave", "keep", "don't touch", "do not touch", "limit to",
    "nothing else", "solely",
}

_PRIOR_TURN_PHRASES = {
    "as we discussed", "continuing from", "as before", "like we", "earlier",
    "previously", "you said", "that you", "the above", "from before", "as mentioned",
    "now ", "then ", "next", "also",
}

_WHY_PHRASES = {"because", "so that", "in order to", "since", "the reason", "so we", "to avoid", "to ensure"}

_TECH_STACK = {
    "python", "javascript", "typescript", "react", "next.js", "nextjs", "fastapi",
    "flask", "django", "node", "sql", "postgres", "sqlite", "sqlalchemy", "pytorch",
    "tensorflow", "docker", "css", "html", "tailwind", "rust", "go ", "java", "c++",
    "api", "endpoint", "component", "hook", "class", "function", "module",
}

_OUTPUT_FORMAT_PHRASES = {
    "return a", "return the", "output", "format", "json", "dict with", "list of",
    "as a table", "csv", "with keys", "schema", "shape", "signature",
}

# --- helpers --------------------------------------------------------------


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_']*", text.lower())


def _sentences(text: str) -> list[str]:
    # Strip fenced code blocks first so code doesn't inflate sentence counts.
    stripped = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    parts = re.split(r"[.!?\n]+", stripped)
    return [p.strip() for p in parts if p.strip()]


def _contains_any(text_low: str, phrases) -> bool:
    return any(p in text_low for p in phrases)


# --- clarity --------------------------------------------------------------


def single_imperative_verb(text: str) -> bool:
    words = _words(text)
    if not words:
        return False
    # Opens with an imperative, or contains exactly one distinct imperative verb.
    if words[0] in _IMPERATIVE_VERBS:
        return True
    found = {w for w in words if w in _IMPERATIVE_VERBS}
    return len(found) == 1


def no_passive_voice(text: str) -> bool:
    # Heuristic: "be/been/is/are/was/were + past participle (…ed/…en)".
    return re.search(r"\b(is|are|was|were|be|been|being)\s+\w+(ed|en)\b", text.lower()) is None


def no_hedge_words(text: str) -> bool:
    return not _contains_any(text.lower(), _HEDGE_WORDS)


def sentence_count_le_5(text: str) -> bool:
    return 1 <= len(_sentences(text)) <= 5


# --- specificity ----------------------------------------------------------


def mentions_file_or_line(text: str) -> bool:
    if re.search(r"\b[\w\-/]+\.(py|js|ts|tsx|jsx|json|md|css|html|sql|txt|yml|yaml|toml)\b", text):
        return True
    return re.search(r"\bline\s+\d+", text.lower()) is not None


def names_exact_function_class(text: str) -> bool:
    # snake_case, camelCase, PascalCase, dotted paths, or `backticked` identifiers.
    if "`" in text:
        return True
    if re.search(r"\b[a-z]+[A-Z][a-zA-Z]*\b", text):        # camelCase
        return True
    if re.search(r"\b[A-Z][a-z]+[A-Z][a-zA-Z]*\b", text):   # PascalCase
        return True
    if re.search(r"\b\w+_\w+\b", text):                      # snake_case
        return True
    return re.search(r"\w+\(\)", text) is not None           # foo()


def has_concrete_output_format(text: str) -> bool:
    return _contains_any(text.lower(), _OUTPUT_FORMAT_PHRASES)


def no_vague_quantifiers(text: str) -> bool:
    words = set(_words(text))
    low = text.lower()
    if words & {w for w in _VAGUE_QUANTIFIERS if " " not in w}:
        return False
    return not _contains_any(low, {w for w in _VAGUE_QUANTIFIERS if " " in w})


# --- context --------------------------------------------------------------


def references_prior_turn(text: str) -> bool:
    return _contains_any(text.lower(), _PRIOR_TURN_PHRASES)


def provides_background_why(text: str) -> bool:
    return _contains_any(text.lower(), _WHY_PHRASES)


def mentions_tech_stack(text: str) -> bool:
    return _contains_any(text.lower(), _TECH_STACK)


# --- constraints ----------------------------------------------------------


def has_negative_constraint(text: str) -> bool:
    return _contains_any(text.lower(), _NEGATIVE_CONSTRAINTS)


def specifies_scope_limit(text: str) -> bool:
    return _contains_any(text.lower(), _SCOPE_LIMIT_PHRASES)


# --- scope ----------------------------------------------------------------


def single_task_focus(text: str) -> bool:
    # One or two imperative verbs = focused; more suggests a multi-task dump.
    found = {w for w in _words(text) if w in _IMPERATIVE_VERBS}
    return len(found) <= 2


def no_compound_and_also(text: str) -> bool:
    low = text.lower()
    if "and also" in low or "as well as" in low:
        return False
    return low.count(" and ") <= 2


def task_size_appropriate(text: str) -> bool:
    # Very long single prompts tend to cram too much in at once.
    return len(_words(text)) <= 200


# --- examples -------------------------------------------------------------


def has_code_block(text: str) -> bool:
    return "```" in text or bool(re.search(r"\n\s{4,}\S", text))


def has_before_after(text: str) -> bool:
    low = text.lower()
    return ("currently" in low and ("want" in low or "should" in low)) or "instead of" in low


def has_inline_example(text: str) -> bool:
    low = text.lower()
    return "e.g." in low or "for example" in low or "like this" in low or "such as" in low


# --- registry -------------------------------------------------------------

# factor -> {signal_name: extractor}. rubric.py applies weights over these.
SIGNALS: dict[str, dict] = {
    "clarity": {
        "single_imperative_verb": single_imperative_verb,
        "no_passive_voice": no_passive_voice,
        "no_hedge_words": no_hedge_words,
        "sentence_count_le_5": sentence_count_le_5,
    },
    "specificity": {
        "mentions_file_or_line": mentions_file_or_line,
        "names_exact_function_class": names_exact_function_class,
        "has_concrete_output_format": has_concrete_output_format,
        "no_vague_quantifiers": no_vague_quantifiers,
    },
    "context": {
        "references_prior_turn": references_prior_turn,
        "provides_background_why": provides_background_why,
        "mentions_tech_stack": mentions_tech_stack,
    },
    "constraints": {
        "has_negative_constraint": has_negative_constraint,
        "specifies_scope_limit": specifies_scope_limit,
    },
    "scope": {
        "single_task_focus": single_task_focus,
        "no_compound_and_also": no_compound_and_also,
        "task_size_appropriate": task_size_appropriate,
    },
    "examples": {
        "has_code_block": has_code_block,
        "has_before_after": has_before_after,
        "has_inline_example": has_inline_example,
    },
}


def extract_signals(text: str) -> dict[str, dict[str, bool]]:
    """Run every signal extractor; return {factor: {signal: bool}}."""
    text = text or ""
    return {
        factor: {name: bool(fn(text)) for name, fn in signals.items()}
        for factor, signals in SIGNALS.items()
    }


# Stable, ordered list of every signal name (used to build a fixed-width vector).
SIGNAL_NAMES: list[str] = [
    f"{factor}.{name}" for factor, signals in SIGNALS.items() for name in signals
]
STRUCTURAL_DIM = len(SIGNAL_NAMES)


def signal_vector(text: str) -> list[float]:
    """Flatten all signals into a fixed-length 0/1 vector (the MLP's structural half)."""
    results = extract_signals(text)
    return [
        1.0 if results[factor][name] else 0.0
        for factor, signals in SIGNALS.items()
        for name in signals
    ]
