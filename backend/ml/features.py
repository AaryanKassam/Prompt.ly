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

# Social scaffolding: costs tokens on the way in and invites a conversational
# (long) reply on the way out, while adding no constraint. Distinct from
# _HEDGE_WORDS, which are about commitment rather than cost.
_FILLER_PHRASES = {
    "can you", "could you", "would you", "will you", "please ", "i want you to",
    "i would like", "i'd like", "if possible", "if you could", "let me know",
    "thanks", "thank you", "i was wondering", "would it be possible",
    "just wondering", "for me", "i need you to", "help me", "is there a way",
    "do you think you can", "i'm trying to", "im trying to",
}

# Phrases that cap the size of the reply. Output dominates the token bill —
# median output on real turns is ~6k tokens against a near-zero uncached input —
# so bounding the response is the single biggest lever a prompt has.
# Every phrase here must be about the *reply's* size. Bare counters like
# "in one" and "in two" are not: they match "fix it in one of the parsers" and
# "refactor in two places", which say nothing about how long the answer should
# be. Each entry carries enough context to be unambiguous on its own.
_RESPONSE_BOUND_PHRASES = {
    "briefly", "in one sentence", "in two sentences", "in three sentences",
    "one sentence", "a few bullets", "bullet points", "bullets",
    "just the", "only the", "no explanation", "no preamble", "don't explain",
    "do not explain", "without explaining", "concise", "at most", "no more than",
    "keep it short", "keep it brief", "keep it under", "tl;dr", "diff only",
    "code only", "one paragraph", "in a sentence", "limit your response",
    "limit the response", "be brief", "short answer",
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


def is_structured(text: str) -> bool:
    """True when a long prompt is organised rather than rambling.

    Headings, bullets, numbered steps and fenced code are what separate a
    deliberate handoff document from a stream of consciousness. Length alone
    used to fail three separate signals, so one long-but-organised prompt was
    punished three times for a single attribute. The length signals below
    exempt structured text; `efficiency.concise_prompt` deliberately does not,
    because a long prompt genuinely does cost more to answer however tidy it is.
    """
    if "```" in text:
        return True
    lines = text.splitlines()
    listed = sum(1 for ln in lines if re.match(r"\s*([-*+]|\d+[.)])\s+\S", ln))
    if listed >= 2:
        return True
    return bool(re.search(r"^\s*#{1,6}\s+\S|^\s*\*\*[^*]+\*\*\s*$", text, re.MULTILINE))


_FOCUSED_SENTENCE_LIMIT = 10  # was 5: a well-formed ask is routinely 6-10 sentences


def sentence_count_focused(text: str) -> bool:
    count = len(_sentences(text))
    if count < 1:
        return False
    return count <= _FOCUSED_SENTENCE_LIMIT or is_structured(text)


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


_TASK_WORD_LIMIT = 350  # was 200, which failed most genuine specifications


def task_size_appropriate(text: str) -> bool:
    # Very long *unstructured* prompts tend to cram too much in at once. A
    # structured brief of the same length is one task described properly.
    return len(_words(text)) <= _TASK_WORD_LIMIT or is_structured(text)


# --- examples -------------------------------------------------------------
#
# Renamed in spirit from "did you paste code" to "is the request grounded in
# something concrete". Pasting a block is one way to ground a request; pointing
# at the file is another, and for an agent that can open the file itself the two
# are equivalent. Demanding the paste made the user do the agent's job, and it
# showed: `examples` averaged 0.8/10 across the corpus, which is not a rubric
# measuring a habit, it is a rubric nobody can pass.
#
# The one case where a paste is genuinely irreplaceable is an error: the exact
# message and stack trace are not in the repository, so `grounds_in_error`
# rewards that specifically rather than rewarding code blocks in general.

_ERROR_MARKERS = (
    "traceback", "stack trace", "stacktrace", "exception", "error:", "errno",
    "failed with", "segfault", "panic:", "assertionerror", "typeerror",
    "valueerror", "syntaxerror", "referenceerror", "cannot read", "undefined is not",
    "exit code", "non-zero exit", "npm err", "fatal:",
)


def grounds_in_concrete(text: str) -> bool:
    """Shows the thing, or says exactly where it lives. Either grounds the ask."""
    if "```" in text or re.search(r"\n\s{4,}\S", text):
        return True
    if "`" in text:                       # inline identifier or path
        return True
    return mentions_file_or_line(text)


def has_before_after(text: str) -> bool:
    low = text.lower()
    if "instead of" in low or "rather than" in low:
        return True
    if re.search(r"\b(currently|right now|today|at the moment|used to)\b", low) and re.search(
        r"\b(want|should|expect|need|instead|now)\b", low
    ):
        return True
    # "X -> Y" is the compact form of the same idea.
    return bool(re.search(r"\S\s*(->|→|=>)\s*\S", text))


def grounds_in_error(text: str) -> bool:
    """Pastes the actual failure. The one thing the agent cannot look up itself."""
    return _contains_any(text.lower(), _ERROR_MARKERS)


def has_inline_example(text: str) -> bool:
    low = text.lower()
    return any(
        m in low
        for m in ("e.g.", "for example", "like this", "such as", "for instance", "example:")
    )


# --- model fit (was a cheaper model enough?) -------------------------------
#
# Not a property of the prompt's wording but of the pairing between the task and
# the model that answered it. Opus costs $5/$25 per million tokens against
# Sonnet's $2/$10, so running a lookup on the heavy model is a 2.5x overspend
# that no amount of prompt polish recovers. The reverse is also a real cost:
# a genuinely hard task on a small model buys retries, and three Haiku attempts
# cost more than one Sonnet answer that lands.
#
# Both signals pass when the model is unknown, so scoring a draft you have not
# sent yet is never penalised for a choice you have not made.

_HEAVY_MODEL_MARKERS = ("opus", "fable", "mythos")
_MID_MODEL_MARKERS = ("sonnet",)
_LIGHT_MODEL_MARKERS = ("haiku",)

# Asks that a small model answers as well as a large one: recall, navigation,
# formatting, and single-step edits with no design content.
_LIGHT_TASK_MARKERS = (
    "what is", "what's", "what does", "where is", "where are", "which file",
    "is there", "does it", "do i", "how do i", "list the", "list all", "show me",
    "show the", "print the", "find the", "look up", "remind me", "explain what",
    "summarize", "summarise", "rename", "typo", "spelling", "format this",
    "add a comment", "what are the", "tell me", "confirm", "check if", "read the",
)

# Asks with genuine design or diagnostic content, where the larger model earns it.
_HEAVY_TASK_MARKERS = (
    "architecture", "refactor", "redesign", "design a", "migrate", "optimi",
    "debug", "why does", "why is", "why are", "race condition", "deadlock",
    "trade-off", "tradeoff", "security", "concurren", "algorithm", "schema",
    "end to end", "end-to-end", "from scratch", "rewrite", "plan the",
    "across the", "throughout the", "implement", "build a",
)


def _model_tier(model: str | None) -> int:
    """3 = Opus-class, 2 = Sonnet-class, 1 = Haiku-class, 0 = unknown."""
    low = (model or "").lower()
    if not low:
        return 0
    if any(m in low for m in _HEAVY_MODEL_MARKERS):
        return 3
    if any(m in low for m in _MID_MODEL_MARKERS):
        return 2
    if any(m in low for m in _LIGHT_MODEL_MARKERS):
        return 1
    return 0


def _task_weight(text: str) -> int:
    """3 = needs the big model, 2 = ordinary work, 1 = a cheaper model would do."""
    low = (text or "").lower()
    words = len(_words(text))
    heavy = sum(1 for m in _HEAVY_TASK_MARKERS if m in low)
    light = sum(1 for m in _LIGHT_TASK_MARKERS if m in low)

    if heavy or words > 120 or is_structured(text):
        return 3
    if light and words <= 40:
        return 1
    if words <= 12 and not heavy:
        return 1
    return 2


def model_not_overpowered(text: str, model: str | None = None) -> bool:
    """False when an Opus-class model answered something Sonnet would have nailed."""
    tier = _model_tier(model)
    if tier == 0:
        return True
    return not (tier == 3 and _task_weight(text) == 1)


def model_not_underpowered(text: str, model: str | None = None) -> bool:
    """False when a Haiku-class model got work that will cost retries."""
    tier = _model_tier(model)
    if tier == 0:
        return True
    return not (tier == 1 and _task_weight(text) == 3)


# --- efficiency (token cost) ----------------------------------------------
#
# These score how many tokens a prompt is likely to *spend*, which is a
# different axis from how good it is. A one-word prompt is cheap to send and
# expensive to answer, because the model explores instead of acting.
#
# Evidence, measured on this machine's own corpus (n=45 scored turns with token
# counts) by Mann-Whitney U against observed output tokens:
#   concise_prompt            p=0.010   median 3.3k vs 14.1k output tokens
#   no_filler_phrases         p=0.094   median 3.7k vs 13.9k
#   bounds_response_size      p=0.563   underpowered (only 5 prompts bound it)
#   no_redundant_restatement  p=0.894   not separated on this corpus
# The last two are kept on principle — both directly cause tokens to be spent —
# but they are not yet demonstrated. See docs in README before reweighting.

_CONCISE_WORD_LIMIT = 60  # calibrated: the strongest split in the corpus above


def concise_prompt(text: str) -> bool:
    """Short enough that the reply stays bounded. Strictest of the length signals."""
    return 0 < len(_words(text)) <= _CONCISE_WORD_LIMIT


def no_filler_phrases(text: str) -> bool:
    return not _contains_any(text.lower(), _FILLER_PHRASES)


def bounds_response_size(text: str) -> bool:
    return _contains_any(text.lower(), _RESPONSE_BOUND_PHRASES)


def no_redundant_restatement(text: str) -> bool:
    """False when two sentences restate each other, paying twice for one idea."""
    sets = [set(_words(s)) for s in _sentences(text)]
    sets = [w for w in sets if len(w) >= 4]
    for i, a in enumerate(sets):
        for b in sets[i + 1:]:
            if len(a & b) / min(len(a), len(b)) >= 0.7:
                return False
    return True


# --- registry -------------------------------------------------------------

# factor -> {signal_name: extractor}. rubric.py applies weights over these.
SIGNALS: dict[str, dict] = {
    "clarity": {
        "single_imperative_verb": single_imperative_verb,
        "no_passive_voice": no_passive_voice,
        "no_hedge_words": no_hedge_words,
        "sentence_count_focused": sentence_count_focused,
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
        "grounds_in_concrete": grounds_in_concrete,
        "has_before_after": has_before_after,
        "grounds_in_error": grounds_in_error,
        "has_inline_example": has_inline_example,
    },
    "efficiency": {
        "concise_prompt": concise_prompt,
        "no_filler_phrases": no_filler_phrases,
        "bounds_response_size": bounds_response_size,
        "no_redundant_restatement": no_redundant_restatement,
    },
    "model_fit": {
        "model_not_overpowered": model_not_overpowered,
        "model_not_underpowered": model_not_underpowered,
    },
}

# Signals that also need to know which model answered the turn. Everything else
# is a pure function of the text, so the registry stays callable with one arg.
MODEL_AWARE: frozenset[str] = frozenset({"model_not_overpowered", "model_not_underpowered"})


def extract_signals(text: str, model: str | None = None) -> dict[str, dict[str, bool]]:
    """Run every signal extractor; return {factor: {signal: bool}}.

    `model` is the model that answered the turn, used only by MODEL_AWARE
    signals. Left None (scoring a draft), those signals pass.
    """
    text = text or ""
    return {
        factor: {
            name: bool(fn(text, model) if name in MODEL_AWARE else fn(text))
            for name, fn in signals.items()
        }
        for factor, signals in SIGNALS.items()
    }


# Stable, ordered list of every signal name (used to build a fixed-width vector).
SIGNAL_NAMES: list[str] = [
    f"{factor}.{name}" for factor, signals in SIGNALS.items() for name in signals
]
STRUCTURAL_DIM = len(SIGNAL_NAMES)


def signal_vector(text: str, model: str | None = None) -> list[float]:
    """Flatten all signals into a fixed-length 0/1 vector (the MLP's structural half)."""
    results = extract_signals(text, model)
    return [
        1.0 if results[factor][name] else 0.0
        for factor, signals in SIGNALS.items()
        for name in signals
    ]
