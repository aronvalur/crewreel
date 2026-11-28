import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Crewreel",
  description: "Your crew films the job. You get back a reel that brings in quote requests.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

// Bare shell: the contractor app (app/(app)) adds its own header; the public quote page (app/q) has none.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
