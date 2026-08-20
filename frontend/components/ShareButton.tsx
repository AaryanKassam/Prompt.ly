"use client";

import { useState } from "react";
import { API_BASE } from "@/lib/api";
import { DownloadIcon } from "./icons";

/**
 * Downloads the redacted report.
 *
 * The link is built here rather than pointing at the endpoint directly so the
 * anonymize choice is explicit at download time — the difference between a file
 * naming your repository and one that doesn't matters more than a click.
 */
export default function ShareButton({ path }: { path?: string }) {
  const [open, setOpen] = useState(false);

  function download(fmt: "html" | "json", anonymize: boolean) {
    const params = new URLSearchParams({ fmt, anonymize: String(anonymize) });
    if (path) params.set("path", path);
    // Endpoint sets Content-Disposition: attachment, so this saves rather than navigates.
    window.location.href = `${API_BASE}/api/projects/share?${params}`;
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex h-11 items-center gap-1.5 rounded-md border border-line
                   px-3 text-sm text-content-muted transition-colors duration-200
                   ease-expo hover:bg-surface-hover hover:text-content"
      >
        <DownloadIcon width={15} height={15} />
        Share
      </button>

      {open && (
        <>
          {/* Click-away layer. */}
          <button
            aria-hidden
            tabIndex={-1}
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-40 cursor-default"
          />
          <div
            className="absolute right-0 z-50 mt-1.5 w-72 rounded-lg border border-line-strong
                       bg-surface-overlay p-3 shadow-raised"
          >
            <p className="text-2xs leading-relaxed text-content-muted">
              Downloads a report containing scores, factor breakdowns and habit
              rates — and <span className="text-content">no prompt text, file
              paths or session titles</span>. Safe to send to someone outside the
              project.
            </p>

            <div className="mt-3 space-y-1.5">
              <button
                onClick={() => download("html", false)}
                className="w-full rounded-md bg-accent px-3 py-2 text-left text-sm
                           font-medium text-canvas transition-colors duration-200
                           ease-expo hover:bg-accent-hover"
              >
                Download report
                <span className="block text-2xs font-normal opacity-80">
                  HTML · opens in a browser, prints to PDF
                </span>
              </button>
              <button
                onClick={() => download("html", true)}
                className="w-full rounded-md border border-line-strong px-3 py-2 text-left
                           text-sm text-content-muted transition-colors duration-200
                           ease-expo hover:bg-surface-hover hover:text-content"
              >
                Download anonymized
                <span className="block text-2xs opacity-80">
                  Same, with the folder name replaced
                </span>
              </button>
              <button
                onClick={() => download("json", true)}
                className="w-full rounded-md px-3 py-1.5 text-left text-2xs
                           text-content-subtle transition-colors duration-200 ease-expo
                           hover:text-content"
              >
                Download JSON instead
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
