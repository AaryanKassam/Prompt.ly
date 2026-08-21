"""The one place Prompt.ly calls a language model.

Everything else — scoring, signals, recommendations, the rule-based rewrite — is
deterministic and runs offline. The API is used for exactly two things that
rules genuinely cannot do:

  * rewriting a weak prompt into a strong one that keeps the user's intent
  * turning a set of measured weaknesses into a personalised playbook

Both are *garnish*: they explain and illustrate scores that were already
computed locally. Scoring never calls the API, because the scorer is the part of
this project worth owning — outsourcing it would make the whole thing a wrapper.

Every entry point degrades to the rule-based path when no key is configured or
the call fails, so the feature is additive and never load-bearing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from pydantic import BaseModel, Field

MODEL = "claude-opus-5"

# Rewriting one prompt is a small, well-specified task; a playbook is longer.
REWRITE_MAX_TOKENS = 4000
PLAYBOOK_MAX_TOKENS = 8000


class LLMUnavailable(RuntimeError):
    """No credentials, SDK missing, or the call failed."""


def _looks_like_real_key(value: str | None) -> bool:
    """Reject the placeholder shipped in .env.example.

    `ANTHROPIC_API_KEY=sk-ant-...` is a non-empty string, so a bare truthiness
    check reports the API as configured and the user only finds out when a call
    401s. Anything containing an ellipsis, or too short to be a real key, is a
    placeholder someone forgot to replace.
    """
    if not value:
        return False
    value = value.strip()
    if "..." in value or "…" in value:
        return False
    if value.lower() in {"changeme", "your-key-here", "todo"}:
        return False
    return len(value) >= 20


def available() -> bool:
    """True when a rewrite could actually be attempted."""
    if os.getenv("PROMPTLY_DISABLE_LLM"):
        return False
    has_key = _looks_like_real_key(os.getenv("ANTHROPIC_API_KEY")) or _looks_like_real_key(
        os.getenv("ANTHROPIC_AUTH_TOKEN")
    )
    # An `ant auth login` profile also works; the SDK resolves it itself.
    if not has_key and not _has_cli_profile():
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _has_cli_profile() -> bool:
    from pathlib import Path

    return (Path.home() / ".config" / "anthropic").is_dir()


def _client():
    try:
        import anthropic
    except ImportError as exc:
        raise LLMUnavailable("the `anthropic` package is not installed") from exc
    try:
        return anthropic.Anthropic()
    except Exception as exc:  # missing/invalid credentials
        raise LLMUnavailable(str(exc)) from exc


# --------------------------------------------------------------------------
# prompt rewriting
# --------------------------------------------------------------------------


class RewrittenPrompt(BaseModel):
    """Schema the model must fill — keeps the response parseable."""

    rewritten: str = Field(description="The improved prompt, ready to paste and send.")
    what_changed: list[str] = Field(
        description="2-4 short phrases naming each concrete change made."
    )
    assumptions: list[str] = Field(
        description=(
            "Any detail invented because the original didn't supply it "
            "(file paths, reasons). Empty list if nothing was invented."
        )
    )


REWRITE_SYSTEM = """\
You rewrite software-engineering prompts so they get better results from a coding assistant.

You are given a weak prompt and a list of measured weaknesses. Rewrite it to fix \
those weaknesses while preserving the author's original intent exactly. Never \
expand the scope of what was asked.

Rules:
- Keep the author's voice and their actual request. You are editing, not redesigning.
- Open with one imperative verb naming the action.
- Where the original lacks a detail you cannot know (a file path, a rationale, a \
concrete example), you may invent a *plausible placeholder* — but you MUST list \
every such invention in `assumptions` so the author can correct it. Never present \
an invented file path as if it were known.
- Prefer specifics over adjectives: "under 200ms" not "faster".
- Keep it under 120 words unless the original was longer.
- Output only the prompt itself in `rewritten` — no preamble, no markdown headers."""


@dataclass
class RewriteResult:
    rewritten: str
    what_changed: list[str]
    assumptions: list[str]
    input_tokens: int
    output_tokens: int

    def as_dict(self) -> dict:
        return {
            "rewritten": self.rewritten,
            "what_changed": self.what_changed,
            "assumptions": self.assumptions,
            "usage": {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens},
        }


def rewrite_prompt(original: str, issues: list[dict]) -> RewriteResult:
    """Ask Claude for a stronger version of one prompt."""
    client = _client()
    weaknesses = "\n".join(f"- {i['label']}: {i['why']}" for i in issues[:8]) or "- none detected"

    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=REWRITE_MAX_TOKENS,
            system=REWRITE_SYSTEM,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Measured weaknesses:\n{weaknesses}\n\n"
                        f"Prompt to rewrite:\n<prompt>\n{original}\n</prompt>"
                    ),
                }
            ],
            output_format=RewrittenPrompt,
        )
    except Exception as exc:
        raise LLMUnavailable(str(exc)) from exc

    if response.stop_reason == "refusal":
        raise LLMUnavailable("the model declined to rewrite this prompt")

    parsed = response.parsed_output
    if parsed is None:
        raise LLMUnavailable("the model returned no parseable output")

    return RewriteResult(
        rewritten=parsed.rewritten.strip(),
        what_changed=parsed.what_changed,
        assumptions=parsed.assumptions,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


# --------------------------------------------------------------------------
# playbook (the Execute button)
# --------------------------------------------------------------------------


PLAYBOOK_SYSTEM = """\
You coach developers on prompting a coding assistant more effectively.

You receive measured statistics about how someone actually prompts — their
weakest habits with the percentage of prompts missing each — plus real examples
of their own low-scoring prompts.

Produce:

- `pattern`: two or three sentences naming the single underlying habit that
  connects their weaknesses. Ground it in the numbers you were given. Not
  generic prompting advice — something only true of this person.

- `rewrites`: one entry per example prompt supplied, in the order given.
  - `label`: 3-6 words naming what the prompt was trying to do, e.g.
    "Push and set up CI". This is the collapsed heading, so make it concrete.
  - `rewritten`: the prompt rewritten well, ready to paste. Preserve their
    original intent exactly; never expand the scope of what was asked. Where a
    detail cannot be known (a file path, a rationale), write a [bracketed slot]
    rather than inventing a fact. Plain text only — no markdown, no code fences.
  - `why`: one sentence on what changed and why it gets a better result.
  - `fixes`: 2-4 short phrases naming the specific weaknesses addressed.

- `template`: a reusable fill-in-the-blank prompt skeleton targeting their
  specific weaknesses, with [bracketed] slots. Plain text, no code fences.

- `habits`: exactly three concrete, checkable things to do tomorrow. Not "be
  more specific" — something they can verify they did.

Address the reader as "you". No preamble and no closing encouragement."""


class PlaybookRewrite(BaseModel):
    label: str = Field(description="3-6 words naming what this prompt was trying to do.")
    rewritten: str = Field(description="The improved prompt, plain text, ready to paste.")
    why: str = Field(description="One sentence on what changed and why it helps.")
    fixes: list[str] = Field(description="2-4 short phrases naming the weaknesses addressed.")


class PlaybookContent(BaseModel):
    pattern: str = Field(description="The single underlying habit connecting their weaknesses.")
    rewrites: list[PlaybookRewrite]
    template: str = Field(description="Reusable prompt skeleton with [bracketed] slots.")
    habits: list[str] = Field(description="Exactly three concrete, checkable habits.")


def render_playbook_markdown(data: dict) -> str:
    """Markdown rendering of the structured playbook, for terminal and MCP output."""
    lines = ["## The pattern", "", data["pattern"], "", "## Your prompts, rewritten", ""]
    for r in data["rewrites"]:
        lines += [f"### {r['label']}", "", "```", r["rewritten"], "```", "", r["why"], ""]
    lines += ["## A template you can reuse", "", "```", data["template"], "```", ""]
    lines += ["## What to do tomorrow", ""]
    lines += [f"{i}. {h}" for i, h in enumerate(data["habits"], 1)]
    return "\n".join(lines)


@dataclass
class PlaybookResult:
    data: dict
    markdown: str
    input_tokens: int
    output_tokens: int

    def as_dict(self) -> dict:
        return {
            "data": self.data,
            "markdown": self.markdown,
            "usage": {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens},
        }


def generate_playbook(report: dict, examples: list[dict]) -> PlaybookResult:
    """Turn a project report's weaknesses into a personalised guide."""
    client = _client()

    weaknesses = "\n".join(
        f"- {r['missed_pct']}% of prompts miss this — {r['advice']} (factor: {r['factor']})"
        for r in report.get("recommendations", [])
    )
    factors = "\n".join(
        f"- {name}: {value}/10" for name, value in (report.get("factors") or {}).items()
        if value is not None
    )
    sample = "\n\n".join(
        f"<prompt score=\"{e['score']}\">\n{e['preview']}\n</prompt>" for e in examples[:4]
    )

    user = (
        f"Overall prompt score: {report.get('overall')}/10 ({report.get('grade')}) "
        f"across {report.get('totals', {}).get('scored_prompts', 0)} prompts.\n\n"
        f"Factor scores:\n{factors}\n\n"
        f"Weakest habits:\n{weaknesses}\n\n"
        f"Their actual low-scoring prompts:\n{sample}"
    )

    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=PLAYBOOK_MAX_TOKENS,
            system=PLAYBOOK_SYSTEM,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            messages=[{"role": "user", "content": user}],
            output_format=PlaybookContent,
        )
    except Exception as exc:
        raise LLMUnavailable(str(exc)) from exc

    if response.stop_reason == "refusal":
        raise LLMUnavailable("the model declined to generate a playbook")

    parsed = response.parsed_output
    if parsed is None:
        raise LLMUnavailable("the model returned no parseable output")

    data = parsed.model_dump()
    # Pair each rewrite with the prompt it came from, by position.
    for rewrite, example in zip(data["rewrites"], examples):
        rewrite["original"] = example.get("preview", "")
        rewrite["score"] = example.get("score")
        rewrite["prompt_id"] = example.get("id")

    return PlaybookResult(
        data=data,
        markdown=render_playbook_markdown(data),
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
