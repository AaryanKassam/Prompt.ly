/**
 * Minimal markdown renderer for LLM-generated playbooks.
 *
 * Handles only what the playbook prompt asks for — headings, fenced code,
 * blockquotes, lists, bold and inline code. Written by hand rather than pulling
 * in a parser because the input shape is fixed and narrow.
 *
 * Everything is escaped before any tag is inserted, so model output can never
 * introduce markup into the page.
 */
function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
  );
}

/** Inline formatting, applied only to already-escaped text. */
function inline(escaped: string): string {
  return escaped
    .replace(/`([^`]+)`/g, '<code class="rounded bg-surface-overlay px-1 py-0.5 text-2xs">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold text-content">$1</strong>');
}

function toHtml(markdown: string): string {
  const out: string[] = [];
  const lines = markdown.split("\n");
  let i = 0;
  let listOpen = false;

  const closeList = () => {
    if (listOpen) {
      out.push("</ul>");
      listOpen = false;
    }
  };

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code — consumed verbatim, never parsed for inline markup.
    if (line.trimStart().startsWith("```")) {
      closeList();
      const body: string[] = [];
      i++;
      // A closing fence is bare by definition, so a fence carrying an info
      // string (```ts) is content from a nested block rather than a terminator.
      while (i < lines.length) {
        const t = lines[i].trimStart();
        const isFence = t.startsWith("```");
        if (isFence && t.slice(3).trim() === "") break;
        body.push(lines[i]);
        i++;
      }
      i++;
      out.push(
        `<pre class="overflow-x-auto rounded-md border border-line bg-surface-raised p-3 my-3"><code class="font-mono text-2xs leading-relaxed">${escapeHtml(
          body.join("\n"),
        )}</code></pre>`,
      );
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      closeList();
      const level = heading[1].length;
      const cls =
        level <= 2
          ? "mt-6 mb-2 text-sm font-semibold text-content"
          : "mt-4 mb-1.5 text-2xs uppercase tracking-wider text-content-subtle";
      out.push(`<h${level} class="${cls}">${inline(escapeHtml(heading[2]))}</h${level}>`);
      i++;
      continue;
    }

    if (line.startsWith(">")) {
      closeList();
      out.push(
        `<blockquote class="my-2 border-l-2 border-line-strong pl-3 text-sm italic text-content-muted">${inline(
          escapeHtml(line.replace(/^>\s?/, "")),
        )}</blockquote>`,
      );
      i++;
      continue;
    }

    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+\.\s+(.*)$/);
    if (bullet || numbered) {
      if (!listOpen) {
        out.push('<ul class="my-2 space-y-1.5 pl-4">');
        listOpen = true;
      }
      out.push(
        `<li class="list-disc text-sm leading-relaxed text-content-muted">${inline(
          escapeHtml((bullet ?? numbered)![1]),
        )}</li>`,
      );
      i++;
      continue;
    }

    if (!line.trim()) {
      closeList();
      i++;
      continue;
    }

    closeList();
    out.push(
      `<p class="my-2 text-sm leading-relaxed text-content-muted">${inline(escapeHtml(line))}</p>`,
    );
    i++;
  }

  closeList();
  return out.join("");
}

export default function Markdown({ children }: { children: string }) {
  return <div dangerouslySetInnerHTML={{ __html: toHtml(children) }} />;
}
