import { createColumnHelper, createSortedRowModel, rowSortingFeature, tableFeatures, useTable } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, CircleAlert, CircleCheck } from "lucide-react";
import { useMemo, useRef } from "react";
import { Bar, BarChart, CartesianGrid, ReferenceLine, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { deviceLabel, reviewReasons } from "@/review";
import type { Device, Tag, TagFile } from "@/types";

interface Row {
  tag: Tag;
  device: Device;
  label: string;
  cabinet: string;
  confidence: number;
  reasons: string[];
}

const features = tableFeatures({ rowSortingFeature, sortedRowModel: createSortedRowModel() });
const helper = createColumnHelper<typeof features, Row>();

const chartConfig = {
  ok: { label: "OK", color: "var(--ok)" },
  review: { label: "Needs review", color: "var(--review)" },
} satisfies ChartConfig;

interface DevicesDialogProps {
  open: boolean;
  onOpenChange(open: boolean): void;
  file: TagFile;
  threshold: number;
  onOpenDevice(tag: Tag, device: Device): void;
}

export function DevicesDialog({ open, onOpenChange, file, threshold, onOpenDevice }: DevicesDialogProps) {
  const pending = useRef<(() => void) | null>(null);
  const openDevice = (r: Row) => {
    pending.current = () => onOpenDevice(r.tag, r.device);
    onOpenChange(false);
  };
  const openRef = useRef(openDevice);
  openRef.current = openDevice;

  const data = useMemo(
    () =>
      file.tags.flatMap((tag) =>
        tag.devices.map((device) => ({
          tag,
          device,
          label: deviceLabel(device),
          cabinet: tag.cabinet,
          confidence: device.confidence,
          reasons: reviewReasons(device, threshold),
        })),
      ),
    [file, threshold],
  );

  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor("label", {
          header: "Device",
          cell: (info) => (
            <Button variant="link" className="h-auto p-0" onClick={() => openRef.current(info.row.original)}>
              {info.getValue()}
            </Button>
          ),
        }),
        helper.accessor("cabinet", { header: "Cabinet" }),
        helper.accessor("confidence", {
          header: "Confidence",
          cell: (info) => <span className="font-mono">{info.getValue().toFixed(3)}</span>,
        }),
        helper.accessor((r) => r.reasons.length, {
          id: "review",
          header: "Review",
          cell: (info) => {
            const reasons = info.row.original.reasons;
            return reasons.length ? (
              <span className="inline-flex items-center gap-1.5 text-review">
                <CircleAlert aria-hidden="true" className="size-4" />
                {reasons.length} {reasons.length === 1 ? "reason" : "reasons"}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-ok">
                <CircleCheck aria-hidden="true" className="size-4" />
                OK
              </span>
            );
          },
        }),
        helper.accessor((r) => r.device.boxes.length, {
          id: "boxes",
          header: "Boxes",
          cell: (info) => <span className="font-mono">{info.getValue()}</span>,
        }),
      ]),
    [],
  );

  const table = useTable({ features, columns, data });

  const chartData = data.map((r) => ({
    id: r.device.device_id,
    label: r.label,
    ok: r.reasons.length ? null : r.confidence,
    review: r.reasons.length ? r.confidence : null,
  }));
  const low = Math.max(0, Math.floor((Math.min(threshold, ...data.map((r) => r.confidence)) - 0.02) * 20) / 20);
  const reviewCount = data.filter((r) => r.reasons.length).length;
  const animate = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const labelOf = new Map(chartData.map((d) => [d.id, d.label]));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[90vh] overflow-y-auto sm:max-w-3xl"
        onCloseAutoFocus={(e) => {
          const action = pending.current;
          pending.current = null;
          if (!action) return;
          e.preventDefault();
          action();
        }}
      >
        <DialogHeader>
          <DialogTitle>Devices</DialogTitle>
          <DialogDescription>
            {data.length} {data.length === 1 ? "device" : "devices"}, {reviewCount} for review at the threshold{" "}
            <span className="font-mono">{threshold.toFixed(2)}</span>. Select a device to open it.
          </DialogDescription>
        </DialogHeader>
        <figure className="flex flex-col gap-1">
          <figcaption className="text-xs text-muted-foreground">
            Device confidence. The dashed line is the review threshold (<span className="font-mono">{threshold.toFixed(2)}</span>).
          </figcaption>
          <ChartContainer
            config={chartConfig}
            className="aspect-auto h-52 w-full"
            role="img"
            aria-label={`Bar chart of the confidence of ${data.length} devices. The review threshold line is at ${threshold.toFixed(2)}.`}
          >
            <BarChart data={chartData} margin={{ top: 16, right: 8, left: 0, bottom: 0 }} accessibilityLayer={false}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="id" tickLine={false} axisLine={false} tickFormatter={(id: string) => labelOf.get(id) ?? id} />
              <YAxis domain={[low, 1]} allowDataOverflow tickLine={false} axisLine={false} width={40} tickFormatter={(v: number) => v.toFixed(2)} />
              <ChartTooltip
                cursor={false}
                content={<ChartTooltipContent labelFormatter={(_, payload) => labelOf.get(payload?.[0]?.payload?.id) ?? ""} />}
              />
              <ChartLegend content={<ChartLegendContent />} />
              <Bar dataKey="ok" stackId="c" fill="var(--color-ok)" radius={4} isAnimationActive={animate} />
              <Bar dataKey="review" stackId="c" fill="var(--color-review)" radius={4} isAnimationActive={animate} />
              <ReferenceLine y={threshold} stroke="var(--foreground)" strokeWidth={1.5} strokeDasharray="4 4" />
            </BarChart>
          </ChartContainer>
        </figure>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id}>
                {group.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  const Icon = sorted === "asc" ? ArrowUp : sorted === "desc" ? ArrowDown : ArrowUpDown;
                  return (
                    <TableHead key={header.id} aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"}>
                      <Button variant="ghost" size="xs" className="-ml-2" onClick={header.column.getToggleSortingHandler()}>
                        <table.FlexRender header={header} />
                        <Icon aria-hidden="true" className={sorted ? "" : "opacity-50"} />
                      </Button>
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                className="cursor-pointer"
                onClick={(e) => (e.target as HTMLElement).closest("button") || openDevice(row.original)}
              >
                {row.getAllCells().map((cell) => (
                  <TableCell key={cell.id}>
                    <table.FlexRender cell={cell} />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </DialogContent>
    </Dialog>
  );
}
