import type { Metadata } from "next";
import { Fira_Code, Fira_Sans } from "next/font/google";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

// Loaded through next/font so the files are self-hosted and there's no
// flash of unstyled text on first paint.
const firaSans = Fira_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-fira-sans",
  display: "swap",
});

const firaCode = Fira_Code({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-fira-code",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Prompt.ly — prompt analytics",
  description:
    "Scores how effectively you prompt Claude, per project. Runs entirely on your machine.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${firaSans.variable} ${firaCode.variable}`}>
      <body className="font-sans">
        {/* Keyboard users get past the nav without tabbing through every link. */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50
                     focus:rounded-md focus:bg-accent focus:px-3 focus:py-2 focus:text-sm
                     focus:font-medium focus:text-canvas"
        >
          Skip to content
        </a>

        <div className="flex min-h-screen">
          <Sidebar />
          <main id="main" className="min-w-0 flex-1">
            <div className="mx-auto max-w-5xl px-5 py-7 md:px-8">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
