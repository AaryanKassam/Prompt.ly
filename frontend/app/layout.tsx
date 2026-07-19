import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Prompt.ly",
  description: "Prompt analytics & efficiency scoring",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-neutral-800">
          <div className="mx-auto max-w-5xl px-6 py-4 flex items-center gap-2">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              <span className="text-brand">Prompt</span>.ly
            </Link>
            <span className="text-xs text-neutral-500 ml-2">
              prompt analytics &amp; efficiency scoring
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
