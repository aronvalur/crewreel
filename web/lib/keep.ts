// Keeps picked/filmed clips on the phone (IndexedDB) until the reel is sent, so a crew can film the
// "before" on arrival, close the app, and film the "after" hours later with the before as a ghost.
// Browser-only. Every call fails soft: no storage just means no memory between visits.
const DB = "crewreel", STORE = "clips";

function open(): Promise<IDBDatabase | null> {
  return new Promise(resolve => {
    try {
      const r = indexedDB.open(DB, 1);
      r.onupgradeneeded = () => r.result.createObjectStore(STORE);
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => resolve(null);
    } catch { resolve(null); }
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T | null> {
  const db = await open();
  if (!db) return null;
  return new Promise(resolve => {
    try {
      const req = fn(db.transaction(STORE, mode).objectStore(STORE));
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch { resolve(null); }
  });
}

type Kept = { blob: Blob; name: string; type: string; at: number };
const key = (tpl: string, slot: string) => `${tpl}:${slot}`;
const MAX_AGE = 3 * 24 * 3600 * 1000;           // a job's clips older than 3 days are stale

export async function keepClip(tpl: string, slot: string, file?: File) {
  if (!file) return tx("readwrite", s => s.delete(key(tpl, slot)));
  return tx("readwrite", s => s.put({ blob: file, name: file.name, type: file.type, at: Date.now() } as Kept, key(tpl, slot)));
}

export async function keptClips(tpl: string, slots: string[]): Promise<Record<string, File>> {
  const out: Record<string, File> = {};
  for (const slot of slots) {
    const k = await tx<Kept>("readonly", s => s.get(key(tpl, slot)) as IDBRequest<Kept>);
    if (k && Date.now() - k.at < MAX_AGE) out[slot] = new File([k.blob], k.name, { type: k.type });
  }
  return out;
}

export async function forgetClips(tpl: string, slots: string[]) {
  for (const slot of slots) await keepClip(tpl, slot);
}
