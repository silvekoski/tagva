import { Boxes, CircleAlert, CircleCheck, Globe, House, MapPin, Package, Table2 } from "lucide-react";
import { useRef } from "react";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from "@/components/ui/command";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { Mode } from "@/player";
import { deviceLabel, isReview } from "@/review";
import type { Device, Manifest, Sweep, Tag, TagFile } from "@/types";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange(open: boolean): void;
  manifest: Manifest;
  file: TagFile | null;
  threshold: number;
  showAll: boolean;
  onSweep(s: Sweep): void;
  onSelect(tag: Tag, device?: Device): void;
  onMode(m: Mode): void;
  onBoxes(): void;
  onTable(): void;
}

export function CommandPalette(p: CommandPaletteProps) {
  const pending = useRef<(() => void) | null>(null);
  const run = (action: () => void) => {
    pending.current = action;
    p.onOpenChange(false);
  };
  const tags = p.file?.tags ?? [];

  return (
    <Dialog open={p.open} onOpenChange={p.onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="top-1/3 translate-y-0 overflow-hidden rounded-xl! p-0 sm:max-w-lg"
        onCloseAutoFocus={(e) => {
          const action = pending.current;
          pending.current = null;
          if (!action) return;
          e.preventDefault();
          action();
        }}
      >
        <DialogHeader className="sr-only">
          <DialogTitle>Search</DialogTitle>
          <DialogDescription>Jump to a scan position, a cabinet or a device, or run a view command.</DialogDescription>
        </DialogHeader>
        <Command label="Search scan positions, cabinets and devices">
          <CommandInput placeholder="Search scan positions, cabinets and devices" />
          <CommandList className="max-h-96">
            <CommandEmpty>No results.</CommandEmpty>
            {tags.some((t) => t.devices.length) && (
              <CommandGroup heading="Devices">
                {tags.flatMap((t) =>
                  t.devices.map((d) => {
                    const review = isReview(d, p.threshold);
                    return (
                      <CommandItem
                        key={d.device_id}
                        value={`device ${d.device_id}`}
                        keywords={[deviceLabel(d), t.cabinet, review ? "review" : "ok"]}
                        onSelect={() => run(() => p.onSelect(t, d))}
                      >
                        {review ? <CircleAlert aria-hidden="true" className="text-review" /> : <CircleCheck aria-hidden="true" className="text-ok" />}
                        <span className="truncate">{deviceLabel(d)}</span>
                        <span className="ml-auto truncate text-xs text-muted-foreground">
                          {t.cabinet}, <span className="font-mono">{d.confidence.toFixed(3)}</span>
                          {review ? ", needs review" : ""}
                        </span>
                      </CommandItem>
                    );
                  }),
                )}
              </CommandGroup>
            )}
            {tags.length > 0 && (
              <CommandGroup heading="Cabinets">
                {tags.map((t) => (
                  <CommandItem key={t.id} value={`cabinet ${t.id}`} keywords={[t.cabinet]} onSelect={() => run(() => p.onSelect(t))}>
                    <Package aria-hidden="true" />
                    <span className="truncate">{t.cabinet}</span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {t.devices.length} {t.devices.length === 1 ? "device" : "devices"}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            <CommandGroup heading="Scan positions">
              {p.manifest.sweeps.map((s) => (
                <CommandItem key={s.id} value={`sweep ${s.id}`} keywords={[s.name, "scan position"]} onSelect={() => run(() => p.onSweep(s))}>
                  <MapPin aria-hidden="true" />
                  <span className="font-mono">{s.id}</span>
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
            <CommandGroup heading="View">
              <CommandItem value="view panorama" onSelect={() => run(() => p.onMode("pano"))}>
                <Globe aria-hidden="true" />
                Panorama mode
              </CommandItem>
              <CommandItem value="view dollhouse" onSelect={() => run(() => p.onMode("dollhouse"))}>
                <House aria-hidden="true" />
                Dollhouse mode
              </CommandItem>
              <CommandItem value="view boxes" onSelect={() => run(p.onBoxes)}>
                <Boxes aria-hidden="true" />
                {p.showAll ? "Hide boxes" : "Show boxes"}
              </CommandItem>
              {p.file && (
                <CommandItem value="view devices table" onSelect={() => run(p.onTable)}>
                  <Table2 aria-hidden="true" />
                  Devices table
                </CommandItem>
              )}
            </CommandGroup>
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
