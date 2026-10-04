import { ExternalLink, FileText, Search } from "lucide-react";
import { useDeferredValue, useRef, useState } from "react";
import { KIND_ICONS, PdfMark } from "@/components/documents-tab";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { KIND_LABELS, KINDS, pageUrl, queryWords, search, useIndexes, wordStarts, type Hit } from "@/documents";
import { cn } from "@/lib/utils";
import type { DocLink } from "@/types";

const MAX_HITS = 80;

interface DocumentLibraryProps {
  open: boolean;
  onOpenChange(open: boolean): void;
  docs: DocLink[];
  deviceType?: string;
  project: string;
  initial?: Hit;
}

const hitKey = (h: Hit) => `${h.doc.url}#${h.page ?? 0}`;

function Marked({ text, words }: { text: string; words: string[] }) {
  if (!words.length) return text;
  return text.split(wordStarts(words)).map((part, i) =>
    i % 2 ? (
      <mark key={i} className="rounded-sm bg-primary/30 text-foreground">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

const filterItem = "h-auto w-full justify-between px-2 py-1.5 font-normal data-[state=on]:bg-accent data-[state=on]:text-accent-foreground";

export function DocumentLibrary({ open, onOpenChange, docs, deviceType, project, initial }: DocumentLibraryProps) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [scope, setScope] = useState("all");
  const [selected, setSelected] = useState<Hit | undefined>(initial);
  const opener = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null);
  const deferred = useDeferredValue(query);
  const indexes = useIndexes(docs);

  const scoped = docs.filter((d) =>
    scope === "device" ? d.kind === "manual" && (!deviceType || d.url.includes(`/devices/${deviceType}/`)) : scope === "project" ? d.kind !== "manual" : true,
  );
  const counts = Object.fromEntries(KINDS.map((k) => [k, scoped.filter((d) => d.kind === k).length]));
  const shown = scoped.filter((d) => kind === "all" || d.kind === kind);
  const words = queryWords(deferred);
  const hits = search(shown, indexes, deferred);
  const src = selected && pageUrl(selected.doc, selected.page);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex h-[88vh] w-[min(96vw,84rem)] flex-col gap-0 p-0 sm:max-w-none"
        onCloseAutoFocus={(e) => {
          e.preventDefault();
          opener.current?.focus();
        }}
      >
        <DialogHeader className="gap-1 border-b px-4 py-3 pr-12">
          <DialogTitle>Document library</DialogTitle>
          <DialogDescription>Search the manuals and open the project documents.</DialogDescription>
          <InputGroup className="mt-2">
            <InputGroupAddon>
              <Search aria-hidden="true" />
            </InputGroupAddon>
            <InputGroupInput
              type="search"
              name="document-search"
              aria-label="Search documents"
              placeholder="Search the text, for example clear or LED"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </InputGroup>
        </DialogHeader>

        <div className="grid min-h-0 flex-1 grid-cols-1 overflow-auto lg:grid-cols-[13rem_minmax(18rem,24rem)_1fr] lg:overflow-hidden">
          <ScrollArea className="min-h-0 border-b lg:border-r lg:border-b-0">
            <div className="flex flex-col gap-4 p-3">
              <div>
                <h3 id="kind-filter" className="mb-1 text-xs font-medium tracking-wider text-muted-foreground uppercase">
                  Kind
                </h3>
                <ToggleGroup
                  type="single"
                  orientation="vertical"
                  aria-labelledby="kind-filter"
                  value={kind}
                  onValueChange={(v) => v && setKind(v)}
                  className="w-full flex-col items-stretch"
                >
                  <ToggleGroupItem value="all" className={filterItem}>
                    All kinds <span className="text-muted-foreground">{scoped.length}</span>
                  </ToggleGroupItem>
                  {KINDS.map((k) => (
                    <ToggleGroupItem key={k} value={k} className={filterItem}>
                      {KIND_LABELS[k]} <span className="text-muted-foreground">{counts[k]}</span>
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
              </div>
              <div>
                <h3 id="scope-filter" className="mb-1 text-xs font-medium tracking-wider text-muted-foreground uppercase">
                  Scope
                </h3>
                <ToggleGroup
                  type="single"
                  orientation="vertical"
                  aria-labelledby="scope-filter"
                  value={scope}
                  onValueChange={(v) => v && setScope(v)}
                  className="w-full flex-col items-stretch"
                >
                  <ToggleGroupItem value="all" className={filterItem}>
                    All documents
                  </ToggleGroupItem>
                  <ToggleGroupItem value="device" className={filterItem}>
                    {deviceType ? `Device type ${deviceType}` : "Device types"}
                  </ToggleGroupItem>
                  <ToggleGroupItem value="project" className={filterItem}>
                    Project {project}
                  </ToggleGroupItem>
                </ToggleGroup>
              </div>
            </div>
          </ScrollArea>

          <div className="flex min-h-0 flex-col border-b max-lg:max-h-[50vh] lg:border-r lg:border-b-0">
            <p aria-live="polite" className="border-b px-3 py-2 text-xs text-muted-foreground">
              {words.length
                ? `${hits.length} ${hits.length === 1 ? "hit" : "hits"}${hits.length > MAX_HITS ? `, first ${MAX_HITS} shown` : ""}`
                : `${hits.length} ${hits.length === 1 ? "document" : "documents"}`}
            </p>
            <ScrollArea className="min-h-0 flex-1">
              {hits.length ? (
                <ul className="flex flex-col gap-1 p-2">
                  {hits.slice(0, MAX_HITS).map((h) => {
                    const Icon = KIND_ICONS[h.doc.kind] ?? FileText;
                    const active = selected && hitKey(selected) === hitKey(h);
                    return (
                      <li key={hitKey(h)}>
                        <button
                          type="button"
                          aria-pressed={!!active}
                          onClick={() => setSelected(h)}
                          className={cn(
                            "flex w-full flex-col gap-1 rounded-md border border-transparent px-2.5 py-2 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
                            active && "border-primary/60 bg-muted",
                          )}
                        >
                          <span className="flex items-center gap-2">
                            <Icon aria-hidden="true" className="size-4 shrink-0 text-primary" />
                            <span className="min-w-0 flex-1 truncate font-medium first-letter:uppercase">{h.doc.title}</span>
                            {h.page && <span className="shrink-0 font-mono text-xs text-muted-foreground">p. {h.page}</span>}
                          </span>
                          {h.chapter && <span className="text-xs text-primary">{h.chapter}</span>}
                          {h.snippet ? (
                            <span className="text-xs leading-relaxed text-muted-foreground">
                              <Marked text={h.snippet} words={words} />
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">{KIND_LABELS[h.doc.kind] ?? h.doc.kind}</span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="p-4 text-center text-muted-foreground">No documents match. Change the search or the filters.</p>
              )}
            </ScrollArea>
          </div>

          <div className="flex min-h-0 flex-col max-lg:min-h-[70vh]">
            {selected && src ? (
              <>
                <div className="flex items-center gap-3 border-b px-3 py-2">
                  <PdfMark className={cn("h-8 w-7", !/\.pdf$/iu.test(selected.doc.url) && "invisible")} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium first-letter:uppercase">{selected.doc.title}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {selected.page ? `Page ${selected.page}${selected.chapter ? `, ${selected.chapter}` : ""}` : (KIND_LABELS[selected.doc.kind] ?? selected.doc.kind)}
                    </p>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <a href={src} target="_blank" rel="noopener">
                      <ExternalLink aria-hidden="true" />
                      Open in new tab
                    </a>
                  </Button>
                </div>
                <iframe
                  key={src}
                  src={src}
                  title={`Preview of ${selected.doc.title}${selected.page ? `, page ${selected.page}` : ""}`}
                  className="min-h-0 w-full flex-1 bg-white max-lg:min-h-[60vh]"
                />
              </>
            ) : (
              <p className="m-auto max-w-xs p-6 text-center text-muted-foreground">Select a document or a search hit to show it here.</p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
