"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { useQuery } from "@/lib/useQuery";
import { FolderIcon, GaugeIcon, LayersIcon, SparkIcon } from "./icons";

const NAV = [
  { href: "/", label: "Overview", Icon: GaugeIcon },
  { href: "/projects", label: "Projects", Icon: FolderIcon },
  { href: "/sessions", label: "Sessions", Icon: LayersIcon },
];

export default function Sidebar() {
  const pathname = usePathname();
  // The detected workspace is cheap and rarely changes — a long stale window
  // keeps it off the critical path on every navigation.
  const { data: ws } = useQuery("workspace", api.activeWorkspace, {
    staleMs: 120_000,
  });

  return (
    <aside
      className="flex shrink-0 flex-col gap-6 border-r border-line bg-surface/40 px-3 py-5
                 md:w-60 md:px-4"
    >
      <Link
        href="/"
        className="flex items-center gap-2 px-2 text-base font-semibold tracking-tight"
      >
        <span className="rounded bg-accent-soft p-1 text-accent">
          <SparkIcon width={15} height={15} />
        </span>
        <span className="hidden md:inline">
          <span className="text-accent">Prompt</span>
          <span className="text-content-muted">.ly</span>
        </span>
      </Link>

      <nav className="flex flex-col gap-0.5">
        {NAV.map(({ href, label, Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm
                          transition-colors duration-200 ease-expo
                          ${
                            active
                              ? "bg-surface-overlay font-medium text-content"
                              : "text-content-muted hover:bg-surface-raised hover:text-content"
                          }`}
            >
              <Icon
                width={16}
                height={16}
                className={active ? "text-accent" : ""}
              />
              <span className="hidden md:inline">{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Where Prompt.ly thinks you're working right now. */}
      {ws?.detected && (
        <div className="mt-auto hidden md:block">
          <div className="eyebrow mb-1.5 px-2.5">Detected workspace</div>
          <Link
            href={`/projects/report?path=${encodeURIComponent(ws.path!)}`}
            className="block rounded-md border border-line bg-surface-raised/60 px-2.5 py-2
                       transition-colors duration-200 ease-expo hover:border-line-strong
                       hover:bg-surface-hover"
          >
            <div className="truncate font-mono text-2xs text-content">
              {ws.path!.split("/").slice(-1)[0]}
            </div>
            <div className="mt-0.5 text-2xs text-content-subtle">
              {ws.editor} · {ws.has_data ? `${ws.prompt_count} prompts` : "no data yet"}
            </div>
          </Link>
        </div>
      )}
    </aside>
  );
}
