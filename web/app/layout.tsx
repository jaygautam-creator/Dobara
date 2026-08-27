import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Dobara — AI Revenue Recovery",
  description: "Recover the payment. Keep the mandate.",
};

const NAV = [
  { href: "/", label: "Thesis" },
  { href: "/control-room", label: "Control Room" },
  { href: "/evidence", label: "Evidence" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      data-theme="dark"
      className={`${geistSans.variable} ${geistMono.variable} antialiased`}
    >
      <body className="bg-surface-0 text-text-primary">
        <header className="sticky top-0 z-40 border-b border-border bg-surface-0/90 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="text-sm font-semibold tracking-tight">
                Dobara <span className="text-text-muted">दोबारा</span>
              </span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-md px-3 py-1.5 text-text-secondary transition-colors hover:bg-surface-1 hover:text-text-primary"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main>{children}</main>
        <footer className="border-t border-border px-6 py-6 text-xs text-text-muted">
          <div className="mx-auto max-w-6xl">
            Razorpay AI Buildathon — Track 03: AI Revenue Recovery. Test mode only. Not
            affiliated with or endorsed by Razorpay.
          </div>
        </footer>
      </body>
    </html>
  );
}
