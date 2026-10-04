import { CircleAlert, CircleCheck, Pencil, TriangleAlert, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode, type Ref } from "react";
import { DocumentsTab } from "@/components/documents-tab";
import { TagEditor } from "@/components/tag-editor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { projectDocs } from "@/documents";
import { cn } from "@/lib/utils";
import type { Selection } from "@/player";
import { deviceLabel, isReview, REASON_LABELS, reviewReasons } from "@/review";
import type { Box, Device, Point3, Tag, TagFile } from "@/types";

const fmtPoint = (p: Point3 | null) => (p ? `${p.x.toFixed(2)}, ${p.y.toFixed(2)}, ${p.z.toFixed(2)}` : "None");

interface DetailsPanelProps {
  ref?: Ref<HTMLElement>;
  file: TagFile;
  selection: Selection;
  threshold: number;
  sweepId: string | null;
  editing: boolean;
  onEditing(v: boolean): void;
  focusToken: number;
  onClose(): void;
  onOpen(tag: Tag, device?: Device): void;
  onShowBox(box: Box): void;
  placeAnchor(): Promise<Point3 | null | undefined>;
  onSave(next: TagFile): Promise<void>;
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="min-w-0 break-words">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Heading({ children }: { children: ReactNode }) {
  return <h3 className="mt-5 mb-2 text-xs font-medium tracking-wider text-muted-foreground uppercase">{children}</h3>;
}

function StatusIcon({ review }: { review: boolean }) {
  const Icon = review ? CircleAlert : CircleCheck;
  return <Icon aria-hidden="true" className={cn("size-4 shrink-0", review ? "text-review" : "text-ok")} />;
}

export function DetailsPanel(p: DetailsPanelProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  const { tag, device } = p.selection;
  const [tab, setTab] = useState("details");
  const allDocs = useMemo(() => projectDocs(p.file), [p.file]);
  const docs = device ? device.documents : allDocs.filter((d) => d.kind !== "manual");

  useEffect(() => {
    heading.current?.focus();
  }, [p.focusToken]);

  return (
    <aside
      ref={p.ref}
      aria-labelledby="panel-title"
      className="flex min-h-0 w-96 shrink-0 flex-col border-l bg-card text-card-foreground max-md:w-full max-md:border-t max-md:border-l-0"
    >
      <div className="flex items-start justify-between gap-2 border-b px-4 py-3">
        <div className="min-w-0">
          <h2
            id="panel-title"
            ref={heading}
            tabIndex={-1}
            className="text-base font-semibold break-words outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {device ? deviceLabel(device) : tag.cabinet}
          </h2>
          <p className="text-muted-foreground">{device ? `${device.device_type} device` : "Cabinet tag"}</p>
        </div>
        <Button variant="ghost" size="icon-sm" aria-label="Close details" onClick={p.onClose}>
          <X aria-hidden="true" />
        </Button>
      </div>
      <Tabs value={tab} onValueChange={setTab} className="min-h-0 flex-1 gap-0">
        <TabsList className="mx-4 mt-3 w-auto self-stretch">
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="documents">
            Documents
            <span className="rounded-sm bg-muted px-1.5 font-mono text-xs text-muted-foreground">{docs.length}</span>
          </TabsTrigger>
        </TabsList>
        <ScrollArea className="min-h-0 flex-1">
          <div className="px-4 pt-3 pb-6">
            <TabsContent value="details">
              {device ? <DeviceBody {...p} tag={tag} device={device} /> : <TagBody {...p} tag={tag} />}
            </TabsContent>
            <TabsContent value="documents">
              <DocumentsTab docs={docs} allDocs={allDocs} deviceType={device?.device_type} project={p.file.project} />
            </TabsContent>
          </div>
        </ScrollArea>
      </Tabs>
    </aside>
  );
}

function TagBody({ tag, threshold, onOpen }: DetailsPanelProps & { tag: Tag }) {
  return (
    <>
      <Facts
        rows={[
          ["Tag ID", <span className="font-mono">{tag.id}</span>],
          ["Path", tag.path.join(" / ")],
          ["Anchor", <span className="font-mono">{fmtPoint(tag.anchor)}</span>],
        ]}
      />
      <Heading>Devices ({tag.devices.length})</Heading>
      {tag.devices.length ? (
        <ul className="flex flex-col gap-1">
          {tag.devices.map((d) => {
            const review = isReview(d, threshold);
            return (
              <li key={d.device_id}>
                <Button variant="ghost" size="sm" className="w-full justify-start" onClick={() => onOpen(tag, d)}>
                  <StatusIcon review={review} />
                  {deviceLabel(d)} ({review ? "review" : "OK"})
                </Button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p>No devices in this cabinet.</p>
      )}
    </>
  );
}

function DeviceBody(p: DetailsPanelProps & { tag: Tag; device: Device }) {
  const { tag, device: d, threshold, sweepId } = p;
  const reasons = reviewReasons(d, threshold);
  return (
    <>
      <Facts
        rows={[
          [
            "Cabinet",
            <Button variant="link" className="h-auto p-0" onClick={() => p.onOpen(tag)}>
              {tag.cabinet}
            </Button>,
          ],
          ["Name", d.name || "None (OCR read no text)"],
          ["Device type", d.device_type],
          ["Confidence", <span className="font-mono">{d.confidence.toFixed(3)}</span>],
          [
            "Review",
            reasons.length ? (
              <Badge variant="outline" className="border-review text-review">
                Yes
              </Badge>
            ) : (
              <Badge variant="outline" className="border-ok text-ok">
                No
              </Badge>
            ),
          ],
          ["Anchor", <span className="font-mono">{fmtPoint(d.anchor)}</span>],
          ["Device ID", <span className="font-mono">{d.device_id}</span>],
        ]}
      />
      {reasons.length > 0 && (
        <>
          <Heading>Review reasons</Heading>
          <ul className="flex flex-col gap-1">
            {reasons.map((r) => (
              <li key={r} className="flex items-center gap-2 text-review">
                <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
                {REASON_LABELS[r] ?? r}
              </li>
            ))}
          </ul>
        </>
      )}
      <Heading>Boxes ({d.boxes.length})</Heading>
      {d.boxes.length ? (
        <ul className="divide-y">
          {d.boxes.map((b, i) => {
            const here = b.scan_position === sweepId;
            return (
              <li
                key={`${b.scan_position}-${i}`}
                className={cn("flex items-center justify-between gap-2 py-1.5 font-mono text-xs", here && "text-primary")}
              >
                <span>
                  {`${b.scan_position}: ${Math.round(b.width)} x ${Math.round(b.height)} px at ${Math.round(b.x)}, ${Math.round(b.y)}` +
                    (b.confidence !== undefined ? `, confidence ${b.confidence.toFixed(3)}` : "") +
                    (here ? " (outlined)" : "")}
                </span>
                <Button variant="outline" size="xs" onClick={() => p.onShowBox(b)} aria-label={`Show the box in ${b.scan_position}`}>
                  Show
                </Button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p>No boxes.</p>
      )}
      {p.editing ? (
        <TagEditor
          key={d.device_id}
          file={p.file}
          tag={tag}
          device={d}
          threshold={threshold}
          placeAnchor={p.placeAnchor}
          onSave={p.onSave}
          onCancel={() => p.onEditing(false)}
        />
      ) : (
        reasons.length > 0 && (
          <Button className="mt-5" onClick={() => p.onEditing(true)}>
            <Pencil aria-hidden="true" />
            Edit device
          </Button>
        )
      )}
    </>
  );
}
