import { h } from "./dom";
import { REASON_LABELS, REASONS, reviewReasons } from "./review";
import type { Device, Point3, Tag, TagFile } from "./types";

export interface Edit {
  name: string;
  cabinet: { id: string } | { name: string };
  anchor: Point3 | null;
  clearReasons: boolean;
}

export interface EditorHost {
  file(): TagFile;
  threshold(): number;
  placeAnchor(): Promise<Point3 | null | undefined>;
  save(file: TagFile): Promise<void>;
  cancel(): void;
}

const NEW = "__new";
const UNASSIGNED = "tag-unassigned";

const mean = (ps: Point3[]): Point3 | null =>
  ps.length
    ? { x: ps.reduce((s, p) => s + p.x, 0) / ps.length, y: ps.reduce((s, p) => s + p.y, 0) / ps.length, z: ps.reduce((s, p) => s + p.z, 0) / ps.length }
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
      to = { id: `tag-${String(n).padStart(3, "0")}`, cabinet: name, anchor: device.anchor && { ...device.anchor }, path: [next.site, name], devices: [] };
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

export function renderEditor(host: EditorHost, tag: Tag, device: Device) {
  const status = h("p", { class: "form-status", role: "status" });
  const name = h("input", { id: "edit-name", value: device.name, autocomplete: "off" });
  const cabinet = h(
    "select",
    { id: "edit-cabinet" },
    host.file().tags.map((t) => h("option", { value: t.id, selected: t.id === tag.id }, t.cabinet)),
    h("option", { value: NEW }, "New cabinet"),
  );
  const newCabinet = h("input", { id: "edit-new-cabinet", autocomplete: "off" });
  const newWrap = h("div", { class: "field", hidden: true }, h("label", { for: "edit-new-cabinet" }, "New cabinet name"), newCabinet);
  cabinet.addEventListener("change", () => {
    newWrap.hidden = cabinet.value !== NEW;
    newCabinet.required = cabinet.value === NEW;
  });
  const axis = (k: keyof Point3) =>
    h("input", { id: `edit-${k}`, type: "number", step: "0.001", inputMode: "decimal", value: device.anchor ? device.anchor[k].toFixed(3) : "" });
  const coords = { x: axis("x"), y: axis("y"), z: axis("z") };
  const place = h("button", { type: "button" }, "Place by click");
  place.addEventListener("click", async () => {
    place.disabled = true;
    place.textContent = "Click a point on the panorama (Esc cancels)";
    status.textContent = "";
    try {
      const p = await host.placeAnchor();
      if (p) for (const k of ["x", "y", "z"] as const) coords[k].value = p[k].toFixed(3);
      else if (p === null) status.textContent = "The scan has no point under that pixel. Try again.";
    } catch (e) {
      status.textContent = `Raycast failed: ${(e as Error).message}`;
    } finally {
      place.disabled = false;
      place.textContent = "Place by click";
    }
  });

  let clear = false;
  const reasons = h("p", { class: "edit-reasons" });
  const showReasons = () => {
    const r = clear ? [] : device.review_reasons.filter((x) => x !== "low_confidence");
    reasons.textContent = r.length ? `Pipeline reasons: ${r.map((x) => REASON_LABELS[x] ?? x).join(", ")}.` : "No pipeline reasons.";
    if (device.confidence < host.threshold()) reasons.textContent += " Low confidence stays while the confidence is below the threshold.";
  };
  showReasons();
  const clearBtn = h("button", { type: "button" }, "Clear review reasons");
  clearBtn.addEventListener("click", () => {
    clear = true;
    clearBtn.disabled = true;
    showReasons();
  });

  const form = h(
    "form",
    { class: "editor", "aria-label": "Edit device" },
    h("h3", {}, "Edit device"),
    h("div", { class: "field" }, h("label", { for: "edit-name" }, "Name"), name),
    h("div", { class: "field" }, h("label", { for: "edit-cabinet" }, "Cabinet"), cabinet),
    newWrap,
    h(
      "fieldset",
      { class: "anchor" },
      h("legend", {}, "Anchor (m, scan frame)"),
      (["x", "y", "z"] as const).map((k) => h("div", { class: "field" }, h("label", { for: `edit-${k}` }, k.toUpperCase()), coords[k])),
      place,
    ),
    reasons,
    clearBtn,
    h("div", { class: "actions" }, h("button", { type: "submit", class: "primary" }, "Save"), h("button", { type: "button", onclick: () => host.cancel() }, "Cancel")),
    status,
  );

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const values = (["x", "y", "z"] as const).map((k) => coords[k].value.trim());
    if (values.some((v) => v) && values.some((v) => !v || !Number.isFinite(Number(v)))) {
      status.textContent = "Enter all three anchor values, or leave all three empty.";
      return;
    }
    if (cabinet.value === NEW && !newCabinet.value.trim()) {
      status.textContent = "Enter a name for the new cabinet.";
      newCabinet.focus();
      return;
    }
    const anchor = values.every((v) => v) ? { x: Number(values[0]), y: Number(values[1]), z: Number(values[2]) } : null;
    const edit: Edit = {
      name: name.value,
      cabinet: cabinet.value === NEW ? { name: newCabinet.value } : { id: cabinet.value },
      anchor,
      clearReasons: clear,
    };
    status.textContent = "Saving";
    try {
      await host.save(applyEdit(host.file(), tag.id, device.device_id, edit, host.threshold()));
    } catch (err) {
      status.textContent = `Save failed: ${(err as Error).message}`;
    }
  });
  return form;
}
