"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useQuery } from "@/lib/useQuery";
import ScoreBadge from "@/components/ScoreBadge";
import ScoreBreakdown from "@/components/ScoreBreakdown";
import NotesEditor from "@/components/NotesEditor";
import { CardListSkeleton, ErrorState, Skeleton } from "@/components/states";
import { ArrowLeftIcon, CheckIcon } from "@/components/icons";

/** Show enough path to disambiguate without wrapping. */
function shortPath(f: string) {
  return f.split("/").slice(-2).join("/");
}

const SIGNAL_LABELS: Record<string, string> = {
  single_imperative_verb: "opens with one action verb",
  no_passive_voice: "active voice",
  no_hedge_words: "no hedging",
  sentence_count_le_5: "5 sentences or fewer",
  mentions_file_or_line: "names a file or line",
  names_exact_function_class: "names exact identifiers",
  has_concrete_output_format: "states output format",
  no_vague_quantifiers: "no vague quantifiers",
  references_prior_turn: "anchors to prior turn",
  provides_background_why: "explains why",
  mentions_tech_stack: "names the stack",
  has_negative_constraint: "says what not to do",
  specifies_scope_limit: "bounds the scope",
  single_task_focus: "one task",
  no_compound_and_also: "no compound asks",
  task_size_appropriate: "right size",
  has_code_block: "includes code",
  has_before_after: "shows before/after",
  has_inline_example: "gives an example",
};

export default function PromptPage({ params }: { params: { id: string } }) {
  const prompt = useQuery(`prompt:${params.id}`, () => api.prompt(params.id), {
    staleMs: 60_000,
  });

  if (prompt.error) {
    return <ErrorState error={prompt.error} onRetry={() => prompt.refetch(true)} />;
  }

  const p = prompt.data;

  if (!p) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-24 w-full" />
        <CardListSkeleton rows={2} />
      </div>
    );
  }

  const diffs = p.file_diffs;
  const hasDiffs =
    diffs.created.length || diffs.edited.length || diffs.deleted.length;

  // Flatten the signal map so met/missed can be listed side by side.
  const signalEntries = Object.entries(p.signals ?? {}).flatMap(
    ([factor, sigs]) =>
      Object.entries(sigs).map(([name, met]) => ({ factor, name, met })),
  );
  const met = signalEntries.filter((s) => s.met);
  const missed = signalEntries.filter((s) => !s.met);

  return (
    <div className="animate-fade-up space-y-6">
      <Link
        href={`/sessions/${p.session_id}`}
        className="inline-flex items-center gap-1.5 text-sm text-content-subtle
                   transition-colors duration-200 ease-expo hover:text-content"
      >
        <ArrowLeftIcon width={15} height={15} />
        Back to session
      </Link>

      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Turn {p.turn_index}
          </h1>
          <p className="mt-1 text-2xs text-content-subtle">
            {p.model ?? "unknown model"}
            {p.timestamp && ` · ${new Date(p.timestamp).toLocaleString()}`}
          </p>
        </div>
        <ScoreBadge score={p.score?.overall ?? null} size="lg" />
      </header>

      <section>
        <h2 className="eyebrow mb-2">Prompt</h2>
        <div className="card whitespace-pre-wrap p-4 text-sm leading-relaxed">
          {p.text || (
            <span className="italic text-content-faint">(no text captured)</span>
          )}
        </div>
      </section>

      {p.score && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="eyebrow">Score breakdown</h2>
            <span className="text-2xs text-content-subtle">
              scored by{" "}
              {p.score.model_phase >= 2
                ? "ML model (MLP + rubric blend)"
                : "rubric"}
            </span>
          </div>
          <div className="card p-5">
            <ScoreBreakdown factors={p.score.factors} />
          </div>
        </section>
      )}

      {signalEntries.length > 0 && (
        <section>
          <h2 className="eyebrow mb-3">
            Signals · {met.length} of {signalEntries.length} met
          </h2>
          <div className="card grid gap-x-6 gap-y-1.5 p-4 sm:grid-cols-2">
            {[...met, ...missed].map((s) => (
              <div
                key={`${s.factor}.${s.name}`}
                className={`flex items-center gap-2 text-sm ${
                  s.met ? "text-content-muted" : "text-content-faint"
                }`}
              >
                {s.met ? (
                  <CheckIcon width={14} height={14} className="shrink-0 text-accent" />
                ) : (
                  <span
                    aria-hidden
                    className="h-3.5 w-3.5 shrink-0 rounded-full border border-line-strong"
                  />
                )}
                <span className={s.met ? "" : "line-through decoration-line-strong"}>
                  {SIGNAL_LABELS[s.name] ?? s.name.replace(/_/g, " ")}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="eyebrow mb-2">What Claude did</h2>
        <div className="card space-y-3 p-4 text-sm">
          <div className="text-content-muted">
            {p.tool_calls.length} tool call
            {p.tool_calls.length !== 1 ? "s" : ""}
            {p.output_tokens != null &&
              ` · ${p.output_tokens.toLocaleString()} output tokens`}
          </div>
          {hasDiffs ? (
            <div className="space-y-1 font-mono text-2xs">
              {diffs.created.map((f) => (
                <div key={`c${f}`} className="text-score-high">
                  + {shortPath(f)}
                </div>
              ))}
              {diffs.edited.map((f) => (
                <div key={`e${f}`} className="text-score-mid">
                  ~ {shortPath(f)}
                </div>
              ))}
              {diffs.deleted.map((f) => (
                <div key={`d${f}`} className="text-score-low">
                  - {shortPath(f)}
                </div>
              ))}
            </div>
          ) : (
            <div className="italic text-content-faint">No file changes.</div>
          )}
        </div>
      </section>

      <section>
        <h2 className="eyebrow mb-2">Notes</h2>
        <NotesEditor
          promptId={p.id}
          initialNote={p.annotation?.note ?? null}
          initialTags={p.annotation?.tags ?? []}
        />
      </section>
    </div>
  );
}
