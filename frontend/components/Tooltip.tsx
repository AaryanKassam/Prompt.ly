"use client";

import { useId, useState } from "react";

/**
 * Hover/focus tooltip for icon-only controls.
 *
 * CSS-only would miss keyboard users, so visibility is driven by focus as well
 * as hover, and the label is wired up with aria-describedby rather than being
 * decorative text. Children must still carry their own aria-label.
 */
export default function Tooltip({
  label,
  children,
  side = "bottom",
}: {
  label: string;
  children: React.ReactNode;
  side?: "top" | "bottom";
}) {
  const [open, setOpen] = useState(false);
  const id = useId();

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocusCapture={() => setOpen(true)}
      onBlurCapture={() => setOpen(false)}
    >
      <span aria-describedby={open ? id : undefined} className="inline-flex">
        {children}
      </span>
      <span
        id={id}
        role="tooltip"
        className={`pointer-events-none absolute left-1/2 z-50 -translate-x-1/2 whitespace-nowrap
                    rounded-md border border-line-strong bg-surface-overlay px-2 py-1
                    text-2xs text-content shadow-raised transition-opacity duration-150 ease-expo
                    ${side === "bottom" ? "top-full mt-1.5" : "bottom-full mb-1.5"}
                    ${open ? "opacity-100" : "opacity-0"}`}
      >
        {label}
      </span>
    </span>
  );
}
