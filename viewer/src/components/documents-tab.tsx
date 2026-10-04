import {
  ArrowLeftRight,
  BellOff,
  BookOpen,
  ClipboardCheck,
  DraftingCompass,
  ExternalLink,
  FileText,
  Library,
  Lightbulb,
  ListTree,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { lazy, Suspense, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { fmtBytes, KIND_LABELS, TASKS, useIndexes, type Hit } from "@/documents";
import type { DocLink } from "@/types";

const DocumentLibrary = lazy(() => import("./document-library").then((m) => ({ default: m.DocumentLibrary })));

export const KIND_ICONS: Record<string, LucideIcon> = {
  manual: BookOpen,
  drawing: DraftingCompass,
  maintenance_report: Wrench,
  inspection_report: ClipboardCheck,
};

const TASK_ICONS: LucideIcon[] = [BellOff, Lightbulb, ListTree, ArrowLeftRight];

export function PdfMark({ className = "h-12 w-10" }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`grid shrink-0 place-items-end rounded-sm border border-primary/40 bg-primary/10 p-1 font-mono text-[10px] font-semibold text-primary ${className}`}
    >
      PDF
    </span>
  );
}

function PdfCover({ url }: { url: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <PdfMark className="h-24 w-[4.5rem]" />;
  return (
    <img
      src={url.replace(/\.pdf$/iu, ".cover.png")}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
      className="h-24 w-[4.5rem] shrink-0 rounded-sm border bg-white object-cover object-top shadow-sm"
    />
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="mb-2 text-xs font-medium tracking-wider text-muted-foreground uppercase">{title}</h3>
      {children}
    </section>
  );
}

const Empty = ({ children }: { children: ReactNode }) => (
  <p className="rounded-md border border-dashed px-3 py-4 text-center text-muted-foreground">{children}</p>
);

const NewTab = () => (
  <>
    <ExternalLink aria-hidden="true" className="size-3.5 shrink-0 text-muted-foreground" />
    <span className="sr-only"> (opens in a new tab)</span>
  </>
);

interface DocumentsTabProps {
  docs: DocLink[];
  allDocs: DocLink[];
  deviceType?: string;
  project: string;
}

export function DocumentsTab({ docs, allDocs, deviceType, project }: DocumentsTabProps) {
  const [library, setLibrary] = useState<{ open: boolean; target?: Hit; key: number }>({ open: false, key: 0 });
  const manuals = docs.filter((d) => d.kind === "manual");
  const projectDocs = docs.filter((d) => d.kind !== "manual");
  const indexes = useIndexes(manuals);
  const tasks = TASKS.flatMap((t, i) =>
    manuals.flatMap((doc) => {
      const entry = indexes.get(doc.url)?.outline.find((o) => o.title === t.section);
      return entry ? [{ ...t, icon: TASK_ICONS[i], doc, page: entry.page, chapter: entry.title }] : [];
    }),
  );

  return (
    <>
      {tasks.length > 0 && (
        <section aria-labelledby="tasks-title">
          <h3 id="tasks-title" className="mb-2 text-xs font-medium tracking-wider text-muted-foreground uppercase">
            Tasks
          </h3>
          <ul className="grid grid-cols-2 gap-2">
            {tasks.map((t) => (
              <li key={t.section} className="contents">
                <Button
                  variant="outline"
                  className="h-auto flex-col items-start gap-1 px-3 py-2 text-left whitespace-normal"
                  onClick={() => setLibrary((l) => ({ open: true, target: { doc: t.doc, page: t.page, chapter: t.chapter }, key: l.key + 1 }))}
                >
                  <span className="flex items-center gap-1.5 font-medium">
                    <t.icon aria-hidden="true" className="size-4 shrink-0 text-primary" />
                    {t.label}
                  </span>
                  <span className="text-xs font-normal text-muted-foreground">Manual, page {t.page}</span>
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <Button variant="secondary" className={tasks.length ? "mt-4 w-full" : "w-full"} onClick={() => setLibrary((l) => ({ open: true, key: l.key + 1 }))}>
        <Library aria-hidden="true" />
        Open library
      </Button>

      {deviceType && (
        <Group title="For this device type">
          {manuals.length ? (
            <ul className="flex flex-col gap-2">
              {manuals.map((doc) => {
                const index = indexes.get(doc.url);
                return (
                  <li key={doc.url}>
                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noopener"
                      className="flex items-center gap-3 rounded-lg border bg-background/40 p-3 outline-none hover:border-primary/60 focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <PdfCover url={doc.url} />
                      <span className="min-w-0 flex-1">
                        <span className="block font-medium break-words first-letter:uppercase">{doc.title}</span>
                        <span className="block text-xs text-muted-foreground">
                          {index ? `${index.pages} pages, ${fmtBytes(index.bytes)}` : "Manual"}
                        </span>
                      </span>
                      <NewTab />
                    </a>
                  </li>
                );
              })}
            </ul>
          ) : (
            <Empty>No manuals for {deviceType}.</Empty>
          )}
        </Group>
      )}

      <Group title={`For project ${project}`}>
        {projectDocs.length ? (
          <ul className="divide-y rounded-lg border">
            {projectDocs.map((doc) => {
              const Icon = KIND_ICONS[doc.kind] ?? FileText;
              return (
                <li key={doc.url}>
                  <a
                    href={doc.url}
                    target="_blank"
                    rel="noopener"
                    className="flex items-center gap-3 px-3 py-2 outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                  >
                    <Icon aria-hidden="true" className="size-4 shrink-0 text-primary" />
                    <span className="min-w-0 flex-1">
                      <span className="block break-words first-letter:uppercase">{doc.title}</span>
                      <span className="block text-xs text-muted-foreground">{KIND_LABELS[doc.kind] ?? doc.kind}</span>
                    </span>
                    <NewTab />
                  </a>
                </li>
              );
            })}
          </ul>
        ) : (
          <Empty>No project documents.</Empty>
        )}
      </Group>

      {library.key > 0 && (
        <Suspense fallback={null}>
          <DocumentLibrary
            key={library.key}
            open={library.open}
            onOpenChange={(open) => setLibrary((l) => ({ ...l, open }))}
            docs={allDocs}
            deviceType={deviceType}
            project={project}
            initial={library.target}
          />
        </Suspense>
      )}
    </>
  );
}
