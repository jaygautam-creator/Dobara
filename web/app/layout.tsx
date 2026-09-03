import type { Metadata } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";
import { MobileNav } from "@/components/MobileNav";
import { TooltipProvider } from "@/components/ui/tooltip";
import { PITCH_VIDEO_URL, REPO_URL } from "@/lib/links";
import "./globals.css";

// Runs before paint so a returning viewer's chosen theme never flashes to the light
// default first. Kept in perfect sync with ThemeToggle's own read of the same key.
// `?theme=light`/`?theme=dark` overrides for this page load only (never written to
// storage) -- docs/10-REDESIGN.md §6 requires contrast verified in BOTH themes, and
// headless Chrome has no toggle to click, so this is the only way to render either
// theme deterministically for a screenshot. The stored preference still wins on the
// next unparameterized load. Light is the default (docs/DECISIONS.md [2026-08-30]) --
// dark is opt-in only, via a stored "dark" preference or `?theme=dark`.
const THEME_INIT_SCRIPT = `
  try {
    var q = new URLSearchParams(window.location.search).get("theme");
    if (q === "light" || q === "dark") {
      document.documentElement.dataset.theme = q;
    } else {
      var t = window.localStorage.getItem("dobara-theme");
      if (t === "dark") document.documentElement.dataset.theme = "dark";
    }
  } catch (e) {}
`;

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// The "dossier" editorial voice, docs/10-REDESIGN.md §3.1 -- page titles, the thesis,
// pull-quotes only. Never body copy, never numbers.
const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  weight: "400",
  style: ["normal", "italic"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Dobara — AI Revenue Recovery",
  description: "Recover the payment. Keep the mandate.",
};

const NAV = [
  { href: "/", label: "Thesis" },
  { href: "/architecture", label: "Architecture" },
  { href: "/control-room", label: "Control Room" },
  { href: "/evidence", label: "Evidence" },
  { href: PITCH_VIDEO_URL, label: "Pitch video", external: true },
  { href: REPO_URL, label: "GitHub", external: true },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable} antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="bg-surface-0 text-text-primary">
        <TooltipProvider>
          <header className="sticky top-0 z-40 border-b border-border bg-surface-0/90 backdrop-blur">
            <div className="relative mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
              <Link href="/" className="flex items-baseline gap-2">
                <span className="text-sm font-semibold tracking-tight">
                  Dobara <span className="text-text-muted">दोबारा</span>
                </span>
              </Link>
              <nav className="hidden items-center gap-1 text-sm lg:flex">
                {NAV.map((item) =>
                  item.external ? (
                    <a
                      key={item.href}
                      href={item.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-md px-3 py-1.5 text-text-secondary transition-colors hover:bg-surface-1 hover:text-text-primary"
                    >
                      {item.label} <span aria-hidden="true">↗</span>
                    </a>
                  ) : (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="rounded-md px-3 py-1.5 text-text-secondary transition-colors hover:bg-surface-1 hover:text-text-primary"
                    >
                      {item.label}
                    </Link>
                  ),
                )}
                <ThemeToggle />
              </nav>
              <div className="flex items-center gap-1 lg:hidden">
                <ThemeToggle />
                <MobileNav items={NAV} />
              </div>
            </div>
          </header>
          <main>{children}</main>
          <footer className="border-t border-border px-6 py-6 text-xs text-text-muted">
            <div className="mx-auto max-w-6xl">
              Built by{" "}
              <a
                href="https://github.com/jaygautam-creator"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-text-secondary"
              >
                Jay Gautam
              </a>{" "}
              for the Razorpay AI Buildathon — Track 03: AI Revenue Recovery. Test mode
              only. Not affiliated with or endorsed by Razorpay. Source on{" "}
              <a
                href={REPO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-text-secondary"
              >
                GitHub
              </a>
              .
            </div>
          </footer>
        </TooltipProvider>
      </body>
    </html>
  );
}
