import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Crewreel",
  description: "Your crew films the job. You get back a reel that brings in quote requests.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="top">
          <div className="wrap">
            <Link href="/" className="brand">Crewreel</Link>
            <Link href="/" className="nav">Reels</Link>
            <Link href="/settings" className="nav">Business</Link>
            <Link href="/jobs/new" className="btn sm">New reel</Link>
          </div>
        </header>
        <main className="wrap">{children}</main>
      </body>
    </html>
  );
}
