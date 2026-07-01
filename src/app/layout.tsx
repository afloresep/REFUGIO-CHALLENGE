import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "REFUGIO Challenge",
  description: "Local REFUGIO replay viewer, templates, and safety review clone.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link className="brand" href="/">
            REFUGIO
          </Link>
          <nav>
            <Link href="/instructions">Instructions</Link>
            <Link href="/templates">Templates</Link>
            <Link href="/review">Review</Link>
            <Link href="/replays/bf4184ae5b49">Replay</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
