import { Boxes, Search, Table2 } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { getRun, getScan, getTags, putTags, startRun } from "./api";
import { AppSidebar, type Job } from "./components/app-sidebar";
import { CommandPalette } from "./components/command-palette";
import { DetailsPanel } from "./components/details-panel";
import { Stage } from "./components/stage";
import { Button } from "./components/ui/button";
import { Kbd } from "./components/ui/kbd";
import { Separator } from "./components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "./components/ui/sidebar";
import { Toaster } from "./components/ui/sonner";
import { Toggle } from "./components/ui/toggle";
import { ToggleGroup, ToggleGroupItem } from "./components/ui/toggle-group";
import { TooltipProvider } from "./components/ui/tooltip";
import { MIN_CONFIDENCE } from "./detect";
import type { Mode, Player, PlayerEvents, Selection } from "./player";
import { isReview } from "./review";
import type { Device, Manifest, Sweep, Tag, TagFile } from "./types";

const DevicesDialog = lazy(() => import("./components/devices-dialog").then((m) => ({ default: m.DevicesDialog })));
const params = new URLSearchParams(location.search);
const isMac = /Mac|iPhone|iPad/u.test(navigator.platform);
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function setParam(key: string, value: string) {
  const url = new URL(location.href);
  if (value) url.searchParams.set(key, value);
  else url.searchParams.delete(key);
  history.replaceState(null, "", url);
}

function resolve(file: TagFile | null, sel: { tagId: string; deviceId?: string } | null): Selection | null {
  if (!file || !sel) return null;
  for (const tag of file.tags) {
    if (sel.deviceId) {
      const device = tag.devices.find((d) => d.device_id === sel.deviceId);
      if (device) return { tag, device };
    } else if (tag.id === sel.tagId) return { tag };
  }
  return null;
}

export function App() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [bootError, setBootError] = useState("");

  useEffect(() => {
    getScan().then(setManifest, (e: Error) => setBootError(`The scan did not load (${e.message}). Start the API on port 8000 and reload the page.`));
  }, []);

  if (!manifest) {
    return (
      <main className="grid h-full place-items-center p-6 text-muted-foreground">
        <p role="status">{bootError || "Loading the scan"}</p>
      </main>
    );
  }
  return <ScanPlayer manifest={manifest} />;
}

function ScanPlayer({ manifest }: { manifest: Manifest }) {
  const [player, setPlayer] = useState<Player | null>(null);
  const [file, setFileState] = useState<TagFile | null>(null);
  const [threshold, setThreshold] = useState(0.9);
  const [sel, setSel] = useState<{ tagId: string; deviceId?: string } | null>(null);
  const [editing, setEditing] = useState(false);
  const [focusToken, setFocusToken] = useState(0);
  const [mode, setMode] = useState<Mode>("pano");
  const [sweep, setSweep] = useState<Sweep | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [project, setProject] = useState(params.get("project") ?? "");
  const [site, setSite] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState<"run" | "detect" | null>(null);
  const [status, setStatus] = useState("");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [tableOpen, setTableOpen] = useState(false);
  const [tableUsed, setTableUsed] = useState(false);
  const statusTimer = useRef(0);
  const returnFocus = useRef<HTMLElement | null>(null);
  const pendingFocus = useRef<string | null>(null);
  const panelRef = useRef<HTMLElement>(null);

  const selection = useMemo(() => resolve(file, sel), [file, sel]);
  const devices = useMemo(() => (file?.tags ?? []).flatMap((t) => t.devices), [file]);
  const reviewCount = devices.filter((d) => isReview(d, threshold)).length;

  const say = useCallback((text: string, ms = 0) => {
    clearTimeout(statusTimer.current);
    setStatus(text);
    if (ms) statusTimer.current = window.setTimeout(() => setStatus(""), ms);
  }, []);

  const applyFile = useCallback((f: TagFile | null) => {
    setFileState(f);
    if (f) {
      setThreshold(f.review_threshold);
      setSite(f.site);
    }
  }, []);

  useEffect(() => {
    if (!selection) setEditing(false);
  }, [selection]);

  useEffect(() => {
    player?.update({ file, threshold, showAll, selection });
  }, [player, file, threshold, showAll, selection]);

  useEffect(() => {
    const key = pendingFocus.current;
    if (key === null || !player) return;
    pendingFocus.current = null;
    player.flush();
    const back =
      (returnFocus.current?.isConnected && !returnFocus.current.hidden && returnFocus.current) ||
      (key && document.querySelector<HTMLElement>(`#overlay [data-key="${key}"]:not([hidden]), #tag-list [data-key="${key}"]`)) ||
      document.getElementById("stage-canvas");
    back?.focus();
    returnFocus.current = null;
  });

  const select = useCallback(
    (tag: Tag, device?: Device, turn = false) => {
      if (!sel) returnFocus.current = document.activeElement as HTMLElement | null;
      if (sel?.tagId !== tag.id || sel.deviceId !== device?.device_id) setEditing(false);
      setSel({ tagId: tag.id, deviceId: device?.device_id });
      setFocusToken((n) => n + 1);
      if (turn) player?.face(tag, device);
    },
    [player, sel],
  );

  const closePanel = useCallback(() => {
    pendingFocus.current = selection?.device?.device_id ?? selection?.tag.id ?? "";
    setSel(null);
    setEditing(false);
  }, [selection]);

  const events = useRef<PlayerEvents>(null!);
  events.current = {
    select: (tag, device) => select(tag, device),
    sweep: (s) => {
      setSweep(s);
      setParam("sweep", s.id);
    },
    mode: setMode,
    status: say,
    escape: (target) => {
      if (selection && !(editing && panelRef.current?.contains(target))) closePanel();
    },
  };

  useEffect(() => {
    if (!player) return;
    const first =
      player.sweepById.get(params.get("sweep") ?? "") ??
      (() => {
        const c = [0, 1, 2].map((i) => manifest.sweeps.reduce((s, w) => s + w.position[i], 0) / manifest.sweeps.length);
        const dist = (s: Sweep) => Math.hypot(...s.position.map((p, i) => p - c[i]));
        return manifest.sweeps.reduce((a, b) => (dist(a) <= dist(b) ? a : b));
      })();
    player.start(first);
  }, [player, manifest]);

  const loadToken = useRef(0);
  const loadTags = useCallback(
    async (name: string) => {
      const token = ++loadToken.current;
      if (!name) {
        applyFile(null);
        return null;
      }
      try {
        const f = await getTags(name);
        if (token === loadToken.current) applyFile(f);
        return f;
      } catch (e) {
        if (token === loadToken.current) {
          applyFile(null);
          say(`The tags did not load: ${(e as Error).message}`, 8000);
        }
        return null;
      }
    },
    [applyFile, say],
  );

  const firstLoad = useRef(true);
  useEffect(() => {
    const delay = firstLoad.current ? 0 : 400;
    firstLoad.current = false;
    const timer = window.setTimeout(() => loadTags(project.trim()), delay);
    return () => clearTimeout(timer);
  }, [project, loadTags]);

  const onProject = (value: string) => {
    if (file && site === file.site) setSite("");
    setProject(value);
    setParam("project", value.trim());
  };

  async function runDetection() {
    const name = project.trim();
    if (!name) {
      setJob({ text: "Enter a project label first." });
      document.getElementById("project")?.focus();
      return;
    }
    setBusy("run");
    const id = toast.loading("Starting the run");
    setJob({ text: "Starting the run", progress: 0 });
    try {
      const { run_id } = await startRun({ project: name, site: site.trim() || name, review_threshold: threshold });
      for (;;) {
        const r = await getRun(run_id);
        if (r.state === "failed") {
          const text = `The run failed: ${r.message || r.step}`;
          setJob({ text });
          toast.error(text, { id });
          break;
        }
        if (r.state === "done") {
          const f = await loadTags(name);
          const n = (f?.tags ?? []).reduce((s, t) => s + t.devices.length, 0);
          const text = `The run is complete. ${plural(n, "device", "devices")} loaded.`;
          setJob({ text, progress: 1 });
          toast.success(text, { id });
          break;
        }
        const text = `${r.step || "Running"}: ${Math.round(r.progress * 100)} %`;
        setJob({ text, progress: r.progress });
        toast.loading(text, { id });
        await new Promise((res) => setTimeout(res, 1000));
      }
    } catch (err) {
      const text = `The run did not complete: ${(err as Error).message}`;
      setJob({ text });
      toast.error(text, { id });
    } finally {
      setBusy(null);
    }
  }

  async function detectInBrowser() {
    if (!player) return;
    setBusy("detect");
    const id = toast.loading("Loading the browser model");
    try {
      const floor = file?.min_confidence ?? MIN_CONFIDENCE;
      const {
        sweep: s,
        found,
        result,
      } = await player.detectInBrowser(floor, (text, fraction) => {
        setJob({ text, progress: fraction });
        toast.loading(text, { id });
      });
      const scores = found.map((x) => x.score.toFixed(2)).join(", ");
      const text =
        `Browser detection on ${s.id}: ${found.length} REX615 ${found.length === 1 ? "plate" : "plates"}${scores ? ` (${scores})` : ""} ` +
        `above ${floor.toFixed(2)}, ${result.tiles} tiles in ${result.seconds.toFixed(1)} s with ${result.backend}. The boxes are cyan.`;
      setJob({ text, progress: 1 });
      toast.success(`Browser detection on ${s.id}: ${plural(found.length, "plate", "plates")}`, { id, description: text });
    } catch (err) {
      const text = `Browser detection failed: ${(err as Error).message}`;
      setJob({ text });
      toast.error(text, { id });
    } finally {
      setBusy(null);
    }
  }

  function toggleBoxes(next: boolean) {
    setShowAll(next);
    if (!player) return;
    player.update({ showAll: next });
    const sid = player.sweep?.id;
    if (next && sid) {
      const n = player.sweepBoxes().length;
      say(`${plural(n, "detected box", "detected boxes")} on ${sid}. Orange needs review, green is OK, cyan is from the browser.`, 6000);
    }
  }

  function openTable() {
    setTableUsed(true);
    setTableOpen(true);
  }

  async function save(next: TagFile) {
    const saved = await putTags(next);
    applyFile(saved);
    setEditing(false);
    setFocusToken((n) => n + 1);
    toast.success("The tag file is saved.");
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const tagEmpty = !project.trim()
    ? "Enter a project label to load its tags."
    : file
      ? "The tag file has no tags."
      : `No tags for ${project.trim()} yet. Press Run detection.`;

  return (
    <TooltipProvider>
      <SidebarProvider className="h-svh min-h-0">
        <a
          href="#stage-canvas"
          className="fixed top-2 left-2 z-50 -translate-y-20 rounded-md bg-primary px-3 py-1.5 text-primary-foreground focus:translate-y-0"
        >
          Skip to the view
        </a>
        <AppSidebar
          manifest={manifest}
          file={file}
          threshold={threshold}
          onThreshold={setThreshold}
          deviceCount={devices.length}
          reviewCount={reviewCount}
          project={project}
          onProject={onProject}
          site={site}
          onSite={setSite}
          busy={busy}
          job={job}
          onRun={runDetection}
          onDetect={detectInBrowser}
          sweepId={sweep?.id ?? null}
          onSweep={(s) => player?.goTo(s)}
          selection={selection}
          onSelect={(t, d) => select(t, d, true)}
          tagEmpty={tagEmpty}
        />
        <SidebarInset className="min-h-0 min-w-0 overflow-hidden">
          <header className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
            <SidebarTrigger />
            <Separator orientation="vertical" className="mr-1 data-vertical:h-5" />
            <p className="mr-auto truncate text-muted-foreground">
              {mode === "pano" ? "Panorama" : "Dollhouse"}
              {mode === "pano" && sweep && (
                <>
                  {" at "}
                  <span className="font-mono text-foreground">{sweep.id}</span>
                </>
              )}
            </p>
            <Toggle variant="outline" size="sm" pressed={showAll} onPressedChange={toggleBoxes}>
              <Boxes aria-hidden="true" />
              Show boxes
            </Toggle>
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              spacing={0}
              aria-label="View mode"
              value={mode}
              onValueChange={(v) => v && player?.setMode(v as Mode)}
            >
              <ToggleGroupItem value="pano">Panorama</ToggleGroupItem>
              <ToggleGroupItem value="dollhouse">Dollhouse</ToggleGroupItem>
            </ToggleGroup>
            <Button variant="outline" size="sm" onClick={openTable} disabled={!file}>
              <Table2 aria-hidden="true" />
              Devices
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPaletteOpen(true)} aria-keyshortcuts={isMac ? "Meta+K" : "Control+K"}>
              <Search aria-hidden="true" />
              Search
              <Kbd aria-hidden="true">{isMac ? "⌘K" : "Ctrl K"}</Kbd>
            </Button>
          </header>
          <div className="flex min-h-0 flex-1 max-md:flex-col">
            <Stage manifest={manifest} events={events} onReady={setPlayer} status={status} mode={mode} />
            {selection && (
              <DetailsPanel
                ref={panelRef}
                file={file!}
                selection={selection}
                threshold={threshold}
                sweepId={mode === "pano" ? (sweep?.id ?? null) : null}
                editing={editing}
                onEditing={setEditing}
                focusToken={focusToken}
                onClose={closePanel}
                onOpen={(t, d) => select(t, d)}
                onShowBox={(b) => player?.showBox(b)}
                placeAnchor={() => player!.placeAnchor()}
                onSave={save}
              />
            )}
          </div>
        </SidebarInset>
      </SidebarProvider>
      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        manifest={manifest}
        file={file}
        threshold={threshold}
        onSweep={(s) => player?.goTo(s)}
        onSelect={(t, d) => select(t, d, true)}
        onMode={(m) => player?.setMode(m)}
        onBoxes={() => toggleBoxes(!showAll)}
        onTable={openTable}
        showAll={showAll}
      />
      {file && tableUsed && (
        <Suspense fallback={null}>
          <DevicesDialog open={tableOpen} onOpenChange={setTableOpen} file={file} threshold={threshold} onOpenDevice={(t, d) => select(t, d, true)} />
        </Suspense>
      )}
      <Toaster position="bottom-right" />
    </TooltipProvider>
  );
}
