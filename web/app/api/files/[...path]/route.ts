// Serves a job's outputs (reel.mp4, poster.jpg) with HTTP range support so the
// video scrubs in Safari/iOS. Only these whitelisted names are ever served.
import { promises as fs, createReadStream } from "fs";
import path from "path";
import { jobDir } from "@/lib/store";

export const runtime = "nodejs";

const SERVABLE: Record<string, string> = { "reel.mp4": "video/mp4", "poster.jpg": "image/jpeg" };

// Node file stream -> web stream with backpressure. Browsers abort range requests all the time
// (seeking, switching tabs); cancel() must stop the file stream, or Node throws
// "Controller is already closed" as an uncaught exception.
function fileStream(file: string, opts?: { start: number; end: number }) {
  const src = createReadStream(file, opts);
  let closed = false;
  return new ReadableStream<Uint8Array>({
    start(c) {
      src.on("data", chunk => {
        if (closed) return;
        c.enqueue(new Uint8Array(chunk as Buffer));
        if ((c.desiredSize ?? 1) <= 0) src.pause();
      });
      src.on("end", () => { if (!closed) { closed = true; c.close(); } });
      src.on("error", e => { if (!closed) { closed = true; c.error(e); } });
    },
    pull() { src.resume(); },
    cancel() { closed = true; src.destroy(); },
  });
}

export async function GET(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const [id, name, ...rest] = (await params).path;
  if (!id || !name || rest.length || !SERVABLE[name]) return new Response("Not found", { status: 404 });
  let file: string;
  try { file = path.join(jobDir(id), name); } catch { return new Response("Not found", { status: 404 }); }
  let size: number;
  try { size = (await fs.stat(file)).size; } catch { return new Response("Not found", { status: 404 }); }

  const download = new URL(req.url).searchParams.has("download");
  const headers: Record<string, string> = {
    "Content-Type": SERVABLE[name],
    "Accept-Ranges": "bytes",
    "Cache-Control": "private, max-age=60",
  };
  if (download) headers["Content-Disposition"] = `attachment; filename="crewreel-${id}${path.extname(name)}"`;

  const range = req.headers.get("range");
  const m = range && /bytes=(\d*)-(\d*)/.exec(range);
  if (m) {
    const start = m[1] ? parseInt(m[1], 10) : Math.max(0, size - parseInt(m[2], 10));
    const end = m[1] && m[2] ? Math.min(parseInt(m[2], 10), size - 1) : size - 1;
    if (start >= size || start > end) {
      return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${size}` } });
    }
    return new Response(fileStream(file, { start, end }), {
      status: 206,
      headers: { ...headers, "Content-Range": `bytes ${start}-${end}/${size}`, "Content-Length": String(end - start + 1) },
    });
  }
  return new Response(fileStream(file), { headers: { ...headers, "Content-Length": String(size) } });
}
