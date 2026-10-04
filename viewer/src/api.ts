import type { Manifest, Point3, RunStatus, SynthSet, SynthSetSummary, TagFile } from "./types";

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      const d = body.detail;
      detail = typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg ?? JSON.stringify(x)).join("; ") : JSON.stringify(d ?? body);
    } catch {
      // body is not JSON
    }
    throw new ApiError(res.status, detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const scanUrl = (path: string) => (path.startsWith("/") ? path : `/scan/${path}`);

export const getScan = () => request<Manifest>("/api/scan");

const tagsUrl = (project: string) => `/api/tags/${encodeURIComponent(project.replace(/[^A-Za-z0-9._-]/gu, "-"))}`;

export async function getTags(project: string): Promise<TagFile | null> {
  try {
    return await request<TagFile>(tagsUrl(project));
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export const putTags = (file: TagFile) => request<TagFile>(tagsUrl(file.project), json("PUT", file));

export const startRun = (body: { project: string; site?: string; review_threshold?: number }) =>
  request<{ run_id: string }>("/api/runs", json("POST", body));

export const getRun = (id: string) => request<RunStatus>(`/api/runs/${encodeURIComponent(id)}`);

export const raycast = (sweep: string, u: number, v: number) =>
  request<{ anchor: Point3 | null }>(`/api/raycast?sweep=${encodeURIComponent(sweep)}&u=${u.toFixed(1)}&v=${v.toFixed(1)}`);

export const getSynthSets = () => request<{ sets: SynthSetSummary[] }>("/api/synth");

export const getSynthSet = (name: string) => request<SynthSet>(`/api/synth/${encodeURIComponent(name)}`);
