import { useEffect, useState } from "react";
import type { DocLink, TagFile } from "./types";

export interface OutlineEntry {
  title: string;
  page: number;
  level: number;
}

export interface ManualIndex {
  pages: number;
  bytes: number;
  outline: OutlineEntry[];
  text: string[];
}

export interface Hit {
  doc: DocLink;
  page?: number;
  chapter?: string;
  snippet?: string;
}

export const KIND_LABELS: Record<string, string> = {
  manual: "Manual",
  drawing: "Drawing",
  maintenance_report: "Maintenance report",
  inspection_report: "Inspection report",
};

export const KINDS = Object.keys(KIND_LABELS);

export const TASKS = [
  { label: "Clear alarms and indications", section: "5.3.1 Clearing and acknowledging via the local HMI" },
  { label: "Read the LEDs", section: "3.2.2 LEDs" },
  { label: "Navigate the menu", section: "4.1.10 Navigating in the menu" },
  { label: "Select local or remote control", section: "4.1.4 Selecting local or remote use" },
];

const isPdf = (url: string) => /\.pdf$/iu.test(url);

const cache = new Map<string, Promise<ManualIndex | null>>();

export function loadIndex(doc: DocLink): Promise<ManualIndex | null> {
  if (!isPdf(doc.url)) return Promise.resolve(null);
  let p = cache.get(doc.url);
  if (!p) {
    p = fetch(doc.url.replace(/\.pdf$/iu, ".index.json"))
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
    cache.set(doc.url, p);
  }
  return p;
}

export const pageUrl = (doc: DocLink, page?: number) => (page && isPdf(doc.url) ? `${doc.url}#page=${page}` : doc.url);

export const fmtBytes = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1e3))} kB`);

export function projectDocs(file: TagFile): DocLink[] {
  const seen = new Map<string, DocLink>();
  for (const t of file.tags) for (const d of t.devices) for (const doc of d.documents) seen.set(doc.url, doc);
  return [...seen.values()];
}

export const chapterAt = (index: ManualIndex, page: number) => index.outline.filter((o) => o.page <= page).at(-1)?.title;

export const queryWords = (q: string) => q.toLowerCase().split(/\s+/u).filter(Boolean);

const escape = (w: string) => w.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");

export const wordStarts = (words: string[]) => new RegExp(`(?<![\\p{L}\\p{N}])(${words.map(escape).join("|")})`, "giu");

function snippet(text: string, words: string[]) {
  const at = text.search(wordStarts(words));
  const start = Math.max(0, at - 70);
  const end = Math.min(text.length, at + 150);
  return `${start > 0 ? "..." : ""}${text.slice(start, end)}${end < text.length ? "..." : ""}`;
}

export function search(docs: DocLink[], indexes: Map<string, ManualIndex | null>, query: string): Hit[] {
  const words = queryWords(query);
  if (!words.length) return docs.map((doc) => ({ doc }));
  const tests = words.map((w) => new RegExp(wordStarts([w]).source, "iu"));
  const matches = (text: string) => tests.every((re) => re.test(text));
  const hits: Hit[] = [];
  for (const doc of docs) {
    if (matches(doc.title)) hits.push({ doc });
    const index = indexes.get(doc.url);
    if (!index) continue;
    index.text.forEach((text, i) => {
      if (matches(text)) hits.push({ doc, page: i + 1, chapter: chapterAt(index, i + 1), snippet: snippet(text, words) });
    });
  }
  return hits;
}

export function useIndexes(docs: DocLink[]) {
  const [indexes, setIndexes] = useState(new Map<string, ManualIndex | null>());
  const key = docs.map((d) => d.url).join("|");
  useEffect(() => {
    let live = true;
    const list = key ? key.split("|") : [];
    Promise.all(list.map((url) => loadIndex({ url, title: "", kind: "" }).then((i) => [url, i] as const))).then((pairs) => {
      if (live) setIndexes(new Map(pairs));
    });
    return () => {
      live = false;
    };
  }, [key]);
  return indexes;
}
