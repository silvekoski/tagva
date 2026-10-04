import { REASONS, reviewReasons } from "./review";
import type { Point3, Tag, TagFile } from "./types";

export interface Edit {
  name: string;
  cabinet: { id: string } | { name: string };
  anchor: Point3 | null;
  clearReasons: boolean;
}

const UNASSIGNED = "tag-unassigned";

const mean = (ps: Point3[]): Point3 | null =>
  ps.length
    ? {
        x: ps.reduce((s, p) => s + p.x, 0) / ps.length,
        y: ps.reduce((s, p) => s + p.y, 0) / ps.length,
        z: ps.reduce((s, p) => s + p.z, 0) / ps.length,
      }
    : null;

export function applyEdit(file: TagFile, tagId: string, deviceId: string, edit: Edit, threshold: number): TagFile {
  const next: TagFile = structuredClone(file);
  const from = next.tags.find((t) => t.id === tagId)!;
  const device = from.devices.find((d) => d.device_id === deviceId)!;
  device.name = edit.name.trim();
  device.anchor = edit.anchor;
  const flags = new Set(edit.clearReasons ? [] : device.review_reasons);
  flags.delete("no_anchor");
  flags.delete("empty_ocr");
  if (!device.anchor) flags.add("no_anchor");
  if (!device.name) flags.add("empty_ocr");
  device.review_reasons = REASONS.filter((r) => flags.has(r));

  let to: Tag | undefined;
  if ("id" in edit.cabinet) {
    const id = edit.cabinet.id;
    to = next.tags.find((t) => t.id === id);
  } else {
    const name = edit.cabinet.name.trim();
    to = next.tags.find((t) => t.cabinet === name);
    if (!to) {
      const n = Math.max(0, ...next.tags.map((t) => Number(/^tag-(\d+)$/.exec(t.id)?.[1] ?? 0))) + 1;
      to = {
        id: `tag-${String(n).padStart(3, "0")}`,
        cabinet: name,
        anchor: device.anchor && { ...device.anchor },
        path: [next.site, name],
        devices: [],
      };
      next.tags.push(to);
    }
  }
  if (to && to !== from) {
    from.devices = from.devices.filter((d) => d !== device);
    to.devices.push(device);
  }

  next.review_threshold = threshold;
  next.tags = next.tags.filter((t) => t.id !== UNASSIGNED || t.devices.length > 0);
  for (const t of next.tags) {
    if (t.id === UNASSIGNED) t.anchor = mean(t.devices.flatMap((d) => (d.anchor ? [d.anchor] : [])));
    for (const d of t.devices) {
      d.review_reasons = reviewReasons(d, threshold);
      d.review = d.review_reasons.length > 0;
    }
  }
  return next;
}
