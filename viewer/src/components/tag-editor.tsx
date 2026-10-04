import { Crosshair, Eraser, Save } from "lucide-react";
import { useState, type FormEvent } from "react";
import { applyEdit } from "@/apply-edit";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { REASON_LABELS } from "@/review";
import type { Device, Point3, Tag, TagFile } from "@/types";

const NEW = "__new";
const AXES = ["x", "y", "z"] as const;

interface TagEditorProps {
  file: TagFile;
  tag: Tag;
  device: Device;
  threshold: number;
  placeAnchor(): Promise<Point3 | null | undefined>;
  onSave(next: TagFile): Promise<void>;
  onCancel(): void;
}

export function TagEditor({ file, tag, device, threshold, placeAnchor, onSave, onCancel }: TagEditorProps) {
  const [name, setName] = useState(device.name);
  const [cabinet, setCabinet] = useState(tag.id);
  const [newCabinet, setNewCabinet] = useState("");
  const [coords, setCoords] = useState(
    () => Object.fromEntries(AXES.map((k) => [k, device.anchor ? device.anchor[k].toFixed(3) : ""])) as Record<(typeof AXES)[number], string>,
  );
  const [clear, setClear] = useState(false);
  const [placing, setPlacing] = useState(false);
  const [status, setStatus] = useState("");

  const pipelineReasons = clear ? [] : device.review_reasons.filter((x) => x !== "low_confidence");
  const reasonText =
    (pipelineReasons.length ? `Pipeline reasons: ${pipelineReasons.map((x) => REASON_LABELS[x] ?? x).join(", ")}.` : "No pipeline reasons.") +
    (device.confidence < threshold ? " Low confidence stays while the confidence is below the threshold." : "");

  async function place() {
    setPlacing(true);
    setStatus("");
    try {
      const p = await placeAnchor();
      if (p) setCoords({ x: p.x.toFixed(3), y: p.y.toFixed(3), z: p.z.toFixed(3) });
      else if (p === null) setStatus("The scan has no point under that pixel. Try again.");
    } catch (e) {
      setStatus(`Raycast failed: ${(e as Error).message}`);
    } finally {
      setPlacing(false);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const values = AXES.map((k) => coords[k].trim());
    if (values.some((v) => v) && values.some((v) => !v || !Number.isFinite(Number(v)))) {
      setStatus("Enter all three anchor values, or leave all three empty.");
      return;
    }
    if (cabinet === NEW && !newCabinet.trim()) {
      setStatus("Enter a name for the new cabinet.");
      document.getElementById("edit-new-cabinet")?.focus();
      return;
    }
    const anchor = values.every((v) => v) ? { x: Number(values[0]), y: Number(values[1]), z: Number(values[2]) } : null;
    setStatus("Saving");
    try {
      await onSave(
        applyEdit(
          file,
          tag.id,
          device.device_id,
          { name, cabinet: cabinet === NEW ? { name: newCabinet } : { id: cabinet }, anchor, clearReasons: clear },
          threshold,
        ),
      );
    } catch (err) {
      setStatus(`Save failed: ${(err as Error).message}`);
    }
  }

  return (
    <form onSubmit={submit} aria-labelledby="edit-title" className="mt-4 flex flex-col gap-3 rounded-lg border bg-muted/40 p-3">
      <h3 id="edit-title" className="text-sm font-semibold">
        Edit device
      </h3>
      <div className="grid gap-1.5">
        <Label htmlFor="edit-name">Name</Label>
        <Input id="edit-name" autoComplete="off" autoFocus value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="edit-cabinet">Cabinet</Label>
        <Select value={cabinet} onValueChange={setCabinet}>
          <SelectTrigger id="edit-cabinet" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {file.tags.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                {t.cabinet}
              </SelectItem>
            ))}
            <SelectItem value={NEW}>New cabinet</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {cabinet === NEW && (
        <div className="grid gap-1.5">
          <Label htmlFor="edit-new-cabinet">New cabinet name</Label>
          <Input id="edit-new-cabinet" autoComplete="off" required value={newCabinet} onChange={(e) => setNewCabinet(e.target.value)} />
        </div>
      )}
      <fieldset className="grid grid-cols-3 gap-2 rounded-md border p-2.5 pt-1">
        <legend className="px-1 text-xs text-muted-foreground">Anchor (m, scan frame)</legend>
        {AXES.map((k) => (
          <div key={k} className="grid gap-1">
            <Label htmlFor={`edit-${k}`}>{k.toUpperCase()}</Label>
            <Input
              id={`edit-${k}`}
              type="number"
              step="0.001"
              inputMode="decimal"
              className="font-mono"
              value={coords[k]}
              onChange={(e) => setCoords((c) => ({ ...c, [k]: e.target.value }))}
            />
          </div>
        ))}
        <Button type="button" variant="outline" size="sm" className="col-span-3 mt-1" disabled={placing} onClick={place}>
          <Crosshair aria-hidden="true" />
          {placing ? "Click a point on the panorama (Esc cancels)" : "Place by click"}
        </Button>
      </fieldset>
      <p className="text-xs text-muted-foreground">{reasonText}</p>
      <Button type="button" variant="outline" size="sm" disabled={clear} onClick={() => setClear(true)}>
        <Eraser aria-hidden="true" />
        Clear review reasons
      </Button>
      <div className="flex gap-2">
        <Button type="submit">
          <Save aria-hidden="true" />
          Save
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
      <p role="status" className="text-sm empty:hidden">
        {status}
      </p>
    </form>
  );
}
