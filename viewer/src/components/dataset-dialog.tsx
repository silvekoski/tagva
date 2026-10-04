import { ChevronLeft, ChevronRight, Info } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { getSynthSet, getSynthSets } from "@/api";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toggle } from "@/components/ui/toggle";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { BoxXyxy, SynthImage, SynthSet, SynthSetSummary } from "@/types";

const PAGE = 120;
const SIZE_BINS = [
  { id: "xs", label: "< 30 px", min: 0, max: 30 },
  { id: "s", label: "30 to 60 px", min: 30, max: 60 },
  { id: "m", label: "60 to 120 px", min: 60, max: 120 },
  { id: "l", label: "> 120 px", min: 120, max: Infinity },
];
const HIST_EDGES = [0, 20, 30, 45, 60, 90, 120, 180, 270, Infinity];
const chartConfig = { boxes: { label: "Boxes", color: "var(--ok)" } } satisfies ChartConfig;

type Split = "all" | "train" | "val";
type Targets = "all" | "with" | "without";
type Light = "all" | "dark" | "lit";

const boxWidth = (b: BoxXyxy) => b[2] - b[0];
const boxSize = (b: BoxXyxy) => `${Math.round(b[2] - b[0])} x ${Math.round(b[3] - b[1])} px`;
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
const setLabel = (s: { name: string; profile: string | null }) => s.profile ?? s.name.replace(/^local-/u, "");

function describe(img: SynthImage) {
  const parts = [`Synthetic image ${img.name}`, img.split, plural(img.boxes.length, "labeled REX615 box", "labeled REX615 boxes")];
  if (img.dark) parts.push("dark scene");
  return parts.join(", ");
}

function BoxOverlay({ img, labels = false, unlabeled = false }: { img: SynthImage; labels?: boolean; unlabeled?: boolean }) {
  const font = img.width / 64;
  const others = unlabeled ? (img.plates ?? []).filter((p) => !p.labeled && p.box) : [];
  return (
    <svg aria-hidden="true" className="pointer-events-none absolute inset-0 size-full" viewBox={`0 0 ${img.width} ${img.height}`}>
      {others.map((p, i) => {
        const [x0, y0, x1, y1] = p.box!;
        return (
          <rect
            key={`u${i}`}
            x={x0}
            y={y0}
            width={x1 - x0}
            height={y1 - y0}
            fill="none"
            stroke="var(--review)"
            strokeWidth={1.5}
            strokeDasharray="4 3"
            vectorEffect="non-scaling-stroke"
          />
        );
      })}
      {img.boxes.map((b, i) => (
        <g key={i}>
          <rect
            x={b[0]}
            y={b[1]}
            width={b[2] - b[0]}
            height={b[3] - b[1]}
            fill="none"
            stroke="var(--ok)"
            strokeWidth={labels ? 2 : 1.5}
            vectorEffect="non-scaling-stroke"
          />
          {labels && (
            <text
              x={b[0]}
              y={b[1] > font * 1.4 ? b[1] - font * 0.35 : b[3] + font}
              fontSize={font}
              fill="var(--ok)"
              stroke="black"
              strokeWidth={font / 5}
              paintOrder="stroke"
              className="font-mono"
            >
              {boxSize(b)}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

function Lightbox({
  images,
  index,
  set,
  onIndex,
  onClose,
}: {
  images: SynthImage[];
  index: number | null;
  set: string;
  onIndex(i: number): void;
  onClose(i: number): void;
}) {
  const [unlabeled, setUnlabeled] = useState(true);
  const last = useRef(0);
  if (index !== null) last.current = index;
  const i = last.current;
  const img = images[i];
  const go = (step: number) => images.length && onIndex((i + step + images.length) % images.length);
  const fmt = (v: number | null | undefined, unit: string, digits = 1, gap = " ") => (v == null ? "n/a" : `${v.toFixed(digits)}${gap}${unit}`);

  return (
    <Dialog open={index !== null && !!img} onOpenChange={(o) => !o && onClose(i)}>
      <DialogContent
        className="flex h-[94svh] w-[min(96vw,90rem)] max-w-none flex-col gap-3 sm:max-w-none"
        onCloseAutoFocus={(e) => {
          e.preventDefault();
          document.querySelector<HTMLElement>(`[data-thumb="${i}"]`)?.focus();
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") go(1);
          else if (e.key === "ArrowLeft") go(-1);
          else return;
          e.preventDefault();
        }}
      >
        {img && (
          <>
            <DialogHeader className="pr-10">
              <DialogTitle className="font-mono">{img.name}</DialogTitle>
              <DialogDescription>
                Image {i + 1} of {images.length} in the filter. Press the left and right arrow keys for the previous and next image.
              </DialogDescription>
            </DialogHeader>
            <div className="flex min-h-0 flex-1 gap-4 max-md:flex-col max-md:overflow-y-auto">
              <div className="relative min-h-[50svh] flex-1 overflow-hidden rounded-lg bg-stage">
                <img src={img.path} alt={describe(img)} decoding="async" className="absolute inset-0 size-full object-contain" />
                <BoxOverlay img={img} labels unlabeled={unlabeled} />
              </div>
              <aside className="flex w-full shrink-0 flex-col gap-3 overflow-y-auto md:w-80" aria-label="Image data">
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => go(-1)} aria-keyshortcuts="ArrowLeft">
                    <ChevronLeft aria-hidden="true" />
                    Previous
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => go(1)} aria-keyshortcuts="ArrowRight">
                    Next
                    <ChevronRight aria-hidden="true" />
                  </Button>
                </div>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                  <dt className="text-muted-foreground">Set</dt>
                  <dd>{set}</dd>
                  <dt className="text-muted-foreground">Split</dt>
                  <dd>{img.split}</dd>
                  <dt className="text-muted-foreground">Size</dt>
                  <dd className="font-mono">
                    {img.width} x {img.height} px
                  </dd>
                  {img.dark !== undefined && (
                    <>
                      <dt className="text-muted-foreground">Lighting</dt>
                      <dd>{img.dark ? "Dark" : "Normal"}</dd>
                      <dt className="text-muted-foreground">Field of view</dt>
                      <dd className="font-mono">{fmt(img.fov_deg, "°", 1, "")}</dd>
                      <dt className="text-muted-foreground">Camera height</dt>
                      <dd className="font-mono">{fmt(img.camera_z, "m", 2)}</dd>
                      <dt className="text-muted-foreground">JPEG quality</dt>
                      <dd className="font-mono">{img.jpeg_quality ?? "n/a"}</dd>
                    </>
                  )}
                </dl>
                <section className="flex flex-col gap-1.5">
                  <h3 className="font-medium">{plural(img.boxes.length, "labeled box", "labeled boxes")}</h3>
                  {img.boxes.length ? (
                    <ul className="flex flex-col gap-0.5 font-mono text-sm">
                      {img.boxes.map((b, k) => (
                        <li key={k}>{boxSize(b)}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground">No REX615 label in this image.</p>
                  )}
                </section>
                {img.plates && (
                  <section className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="font-medium">{plural(img.plates.length, "plate in the scene", "plates in the scene")}</h3>
                      <Toggle variant="outline" size="sm" pressed={unlabeled} onPressedChange={setUnlabeled}>
                        Unlabeled
                      </Toggle>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Solid green: a labeled REX615 box. Dashed amber: a plate with no label, for example a narrow615 decoy or a REX615 that
                      is too small, too dark or hidden.
                    </p>
                    <ul className="flex flex-col gap-2 text-sm">
                      {img.plates.map((p, k) => (
                        <li key={k} className="rounded-md border p-2">
                          <p className="flex justify-between gap-2">
                            <span className="font-mono">{p.kind}</span>
                            <span className={p.labeled ? "text-ok" : "text-review"}>{p.labeled ? "Labeled" : (p.drop_reason ?? "No label")}</span>
                          </p>
                          <p className="font-mono text-xs text-muted-foreground">
                            width {fmt(p.width_px, "px")}, distance {fmt(p.distance_m, "m", 2)}, angle {fmt(p.off_normal_deg, "°", 1, "")}
                            {p.visible != null && `, visible ${Math.round(p.visible * 100)} %`}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </aside>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function SizeHistogram({ images }: { images: SynthImage[] }) {
  const data = useMemo(() => {
    const counts = HIST_EDGES.slice(0, -1).map((lo, k) => {
      const hi = HIST_EDGES[k + 1];
      return { bin: hi === Infinity ? `${lo}+` : `${lo}-${hi}`, lo, hi, boxes: 0 };
    });
    for (const img of images)
      for (const b of img.boxes) {
        const w = boxWidth(b);
        const c = counts.find((x) => w >= x.lo && w < x.hi);
        if (c) c.boxes++;
      }
    return counts;
  }, [images]);
  const total = data.reduce((s, d) => s + d.boxes, 0);
  const animate = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return (
    <figure className="flex flex-col gap-1">
      <figcaption className="text-xs text-muted-foreground">Labeled box width in px, {plural(total, "box", "boxes")} in the filter.</figcaption>
      <ChartContainer
        config={chartConfig}
        className="aspect-auto h-36 w-full"
        role="img"
        aria-label={`Histogram of labeled box width: ${data.map((d) => `${d.bin} px ${d.boxes}`).join(", ")}.`}
      >
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} accessibilityLayer={false}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="bin" tickLine={false} axisLine={false} interval={0} />
          <YAxis tickLine={false} axisLine={false} width={36} allowDecimals={false} />
          <ChartTooltip cursor={false} content={<ChartTooltipContent labelFormatter={(v) => `${v} px`} />} />
          <Bar dataKey="boxes" fill="var(--color-boxes)" radius={3} isAnimationActive={animate} />
        </BarChart>
      </ChartContainer>
    </figure>
  );
}

export function DatasetDialog({ open, onOpenChange }: { open: boolean; onOpenChange(open: boolean): void }) {
  const [sets, setSets] = useState<SynthSetSummary[] | null>(null);
  const [loaded, setLoaded] = useState<Record<string, SynthSet>>({});
  const [error, setError] = useState("");
  const [active, setActive] = useState("");
  const [split, setSplit] = useState<Split>("all");
  const [targets, setTargets] = useState<Targets>("all");
  const [light, setLight] = useState<Light>("all");
  const [sizes, setSizes] = useState<string[]>([]);
  const [limit, setLimit] = useState(PAGE);
  const [index, setIndex] = useState<number | null>(null);

  useEffect(() => {
    getSynthSets().then(
      (r) => {
        setSets(r.sets);
        setActive((a) => a || (r.sets.find((s) => s.profile === "base") ?? r.sets[0])?.name || "");
      },
      (e: Error) => setError(`The dataset list did not load: ${e.message}`),
    );
  }, []);

  useEffect(() => {
    if (!active || loaded[active]) return;
    getSynthSet(active).then(
      (s) => setLoaded((m) => ({ ...m, [active]: s })),
      (e: Error) => setError(`The set ${active} did not load: ${e.message}`),
    );
  }, [active, loaded]);

  const current = loaded[active];
  const filtered = useMemo(() => {
    const bins = SIZE_BINS.filter((b) => sizes.includes(b.id));
    return (current?.images ?? []).filter(
      (img) =>
        (split === "all" || img.split === split) &&
        (targets === "all" || (targets === "with") === img.boxes.length > 0) &&
        (light === "all" || (light === "dark") === !!img.dark) &&
        (!bins.length || img.boxes.some((b) => bins.some((bin) => boxWidth(b) >= bin.min && boxWidth(b) < bin.max))),
    );
  }, [current, split, targets, light, sizes]);

  useEffect(() => setLimit(PAGE), [active, split, targets, light, sizes]);

  const boxCount = filtered.reduce((s, img) => s + img.boxes.length, 0);
  const shown = filtered.slice(0, limit);
  const summary = sets?.find((s) => s.name === active);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-svh max-h-svh w-screen max-w-none flex-col gap-3 rounded-none sm:max-w-none">
        <DialogHeader className="pr-10">
          <DialogTitle>Training data</DialogTitle>
          <DialogDescription className="flex items-start gap-2">
            <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>
              Local sample of the generator. The training sets were rendered on the GPU instance and are not stored here. These images come
              from the same generator and profiles with other seeds. Green boxes are the YOLO labels.
            </span>
          </DialogDescription>
        </DialogHeader>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        {sets && !sets.length && <p>No synthetic sets in data/synth. Render a set with synth/render.py.</p>}
        {!!sets?.length && (
          <div className="flex min-h-0 flex-1 flex-col gap-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <Tabs value={active} onValueChange={setActive}>
                <TabsList aria-label="Profile">
                  {sets.map((s) => (
                    <TabsTrigger key={s.name} value={s.name}>
                      {setLabel(s)} <span className="font-mono text-xs text-muted-foreground">{s.count}</span>
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
              <ToggleGroup type="single" variant="outline" size="sm" spacing={0} aria-label="Split" value={split} onValueChange={(v) => v && setSplit(v as Split)}>
                <ToggleGroupItem value="all">All splits</ToggleGroupItem>
                <ToggleGroupItem value="train">Train</ToggleGroupItem>
                <ToggleGroupItem value="val">Val</ToggleGroupItem>
              </ToggleGroup>
              <ToggleGroup
                type="single"
                variant="outline"
                size="sm"
                spacing={0}
                aria-label="REX615 labels"
                value={targets}
                onValueChange={(v) => v && setTargets(v as Targets)}
              >
                <ToggleGroupItem value="all">All images</ToggleGroupItem>
                <ToggleGroupItem value="with">Has REX615</ToggleGroupItem>
                <ToggleGroupItem value="without">No REX615</ToggleGroupItem>
              </ToggleGroup>
              <ToggleGroup type="single" variant="outline" size="sm" spacing={0} aria-label="Lighting" value={light} onValueChange={(v) => v && setLight(v as Light)}>
                <ToggleGroupItem value="all">All light</ToggleGroupItem>
                <ToggleGroupItem value="dark">Dark</ToggleGroupItem>
                <ToggleGroupItem value="lit">Normal</ToggleGroupItem>
              </ToggleGroup>
              <ToggleGroup type="multiple" variant="outline" size="sm" spacing={0} aria-label="Box width" value={sizes} onValueChange={setSizes}>
                {SIZE_BINS.map((b) => (
                  <ToggleGroupItem key={b.id} value={b.id}>
                    {b.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </div>
            <p role="status" className="text-sm text-muted-foreground">
              {current
                ? `${filtered.length} of ${plural(current.count, "image", "images")}, ${plural(boxCount, "labeled box", "labeled boxes")}` +
                  (summary ? `. The set has ${summary.train} train and ${summary.val} val images.` : ".")
                : "Loading the set"}
            </p>
            <div className="min-h-0 flex-1 overflow-y-auto pr-1">
              {current && <SizeHistogram images={filtered} />}
              <ul className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(10rem,1fr))] gap-2">
                {shown.map((img, i) => (
                  <li key={img.path}>
                    <button
                      type="button"
                      data-thumb={i}
                      onClick={() => setIndex(i)}
                      className="group flex w-full flex-col gap-1 rounded-lg p-1 text-left outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    >
                      <span className="relative block aspect-square w-full overflow-hidden rounded-md bg-stage">
                        <img src={img.thumb} alt={describe(img)} loading="lazy" decoding="async" className="absolute inset-0 size-full object-contain" />
                        <BoxOverlay img={img} />
                      </span>
                      <span aria-hidden="true" className="flex justify-between gap-1 font-mono text-xs text-muted-foreground">
                        <span className="truncate">{img.name}</span>
                        <span className="shrink-0">
                          {img.split}, {plural(img.boxes.length, "box", "boxes")}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              {current && !filtered.length && <p className="py-6 text-center text-muted-foreground">No image matches the filters.</p>}
              {filtered.length > limit && (
                <div className="flex justify-center py-4">
                  <Button variant="outline" onClick={() => setLimit((n) => n + PAGE)}>
                    Show {Math.min(PAGE, filtered.length - limit)} more
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}
        <Lightbox
          images={filtered}
          index={index}
          set={summary ? setLabel(summary) : active}
          onIndex={(i) => {
            setLimit((n) => Math.max(n, Math.ceil((i + 1) / PAGE) * PAGE));
            setIndex(i);
          }}
          onClose={() => setIndex(null)}
        />
      </DialogContent>
    </Dialog>
  );
}
