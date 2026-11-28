"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Re-renders the server page when the worker moves the job forward.
export default function Poll({ id, status, stage }: { id: string; status: string; stage: string }) {
  const router = useRouter();
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const r = await fetch(`/api/jobs/${id}`, { cache: "no-store" });
        const j = await r.json();
        if (j.status !== status || (j.stage || "") !== stage) router.refresh();
      } catch { /* offline: try again next tick */ }
    }, 2000);
    return () => clearInterval(t);
  }, [id, status, stage, router]);
  return null;
}
