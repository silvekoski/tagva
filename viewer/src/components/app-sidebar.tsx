import { ChevronRight, CircleAlert, CircleCheck, Cpu, LoaderCircle, Play, ScanLine } from "lucide-react";
import type { FormEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import { Slider } from "@/components/ui/slider";
import type { Selection } from "@/player";
import { deviceLabel, isReview } from "@/review";
import type { Device, Manifest, Sweep, Tag, TagFile } from "@/types";

export interface Job {
  text: string;
  progress?: number;
}

interface AppSidebarProps {
  manifest: Manifest;
  file: TagFile | null;
  threshold: number;
  onThreshold(v: number): void;
  deviceCount: number;
  reviewCount: number;
  project: string;
  onProject(v: string): void;
  site: string;
  onSite(v: string): void;
  busy: "run" | "detect" | null;
  job: Job | null;
  onRun(): void;
  onDetect(): void;
  sweepId: string | null;
  onSweep(s: Sweep): void;
  selection: Selection | null;
  onSelect(tag: Tag, device?: Device): void;
  tagEmpty: string;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Collapsible defaultOpen className="group/collapsible">
      <SidebarGroup>
        <SidebarGroupLabel asChild>
          <CollapsibleTrigger className="w-full hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
            {title}
            <ChevronRight aria-hidden="true" className="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-90" />
          </CollapsibleTrigger>
        </SidebarGroupLabel>
        <CollapsibleContent>
          <SidebarGroupContent>{children}</SidebarGroupContent>
        </CollapsibleContent>
      </SidebarGroup>
    </Collapsible>
  );
}

export function AppSidebar(p: AppSidebarProps) {
  const { isMobile, setOpenMobile } = useSidebar();
  const pick = (action: () => void) => {
    if (isMobile) setOpenMobile(false);
    action();
  };
  const selectedKey = p.selection?.device?.device_id ?? p.selection?.tag.id;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    p.onRun();
  };

  return (
    <Sidebar>
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-1">
          <ScanLine aria-hidden="true" className="size-5 text-primary" />
          <h1 className="text-sm font-semibold">REX615 scan player</h1>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Detection</SidebarGroupLabel>
          <SidebarGroupContent>
            <form onSubmit={submit} className="flex flex-col gap-3 px-2">
              <div className="grid gap-1.5">
                <Label htmlFor="project">Project</Label>
                <Input
                  id="project"
                  name="project"
                  autoComplete="off"
                  spellCheck={false}
                  required
                  value={p.project}
                  onChange={(e) => p.onProject(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="site">Site</Label>
                <Input
                  id="site"
                  name="site"
                  autoComplete="off"
                  spellCheck={false}
                  placeholder={p.project.trim()}
                  value={p.site}
                  onChange={(e) => p.onSite(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Button type="submit" disabled={p.busy === "run"}>
                  {p.busy === "run" ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : <Play aria-hidden="true" />}
                  Run detection
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={p.busy === "detect"}
                  onClick={p.onDetect}
                  title="Run the REX615 detector in this browser on the current panorama"
                >
                  {p.busy === "detect" ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : <Cpu aria-hidden="true" />}
                  Detect in browser
                </Button>
              </div>
              <div role="status" aria-live="polite" className="flex flex-col gap-1.5 empty:hidden">
                {p.job && (
                  <>
                    <p className="text-xs text-muted-foreground">{p.job.text}</p>
                    {p.job.progress !== undefined && <Progress value={p.job.progress * 100} aria-label="Job progress" />}
                  </>
                )}
              </div>
            </form>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarSeparator />
        <SidebarGroup>
          <SidebarGroupLabel>Review</SidebarGroupLabel>
          <SidebarGroupContent className="flex flex-col gap-2.5 px-2">
            <div className="flex items-center justify-between">
              <Label asChild>
                <span id="threshold-label">Review threshold</span>
              </Label>
              <output htmlFor="threshold" className="font-mono text-sm">
                {p.threshold.toFixed(2)}
              </output>
            </div>
            <Slider
              id="threshold"
              aria-labelledby="threshold-label"
              min={0}
              max={1}
              step={0.01}
              value={[p.threshold]}
              onValueChange={([v]) => p.onThreshold(v)}
            />
            <p className="text-xs text-muted-foreground">
              <span className="font-mono font-semibold text-foreground">{p.deviceCount}</span> devices,{" "}
              <span className="font-mono font-semibold text-foreground">{p.reviewCount}</span> for review
            </p>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarSeparator />
        <nav aria-label="Scan positions and tags">
          <Section title="Scan positions">
            <ol className="grid grid-cols-3 gap-1 px-1" aria-label="Scan positions">
              {p.manifest.sweeps.map((s) => (
                <li key={s.id}>
                  <SidebarMenuButton
                    size="sm"
                    className="justify-center font-mono"
                    isActive={s.id === p.sweepId}
                    aria-current={s.id === p.sweepId ? "location" : undefined}
                    onClick={() => pick(() => p.onSweep(s))}
                  >
                    {s.id}
                  </SidebarMenuButton>
                </li>
              ))}
            </ol>
          </Section>
          <SidebarSeparator />
          <Section title="Tags">
            {!p.file?.tags.length && <p className="px-2 text-xs text-muted-foreground">{p.tagEmpty}</p>}
            <SidebarMenu id="tag-list">
              {(p.file?.tags ?? []).map((t) => (
                <SidebarMenuItem key={t.id}>
                  <SidebarMenuButton
                    data-key={t.id}
                    isActive={selectedKey === t.id}
                    aria-current={selectedKey === t.id ? "true" : undefined}
                    onClick={() => pick(() => p.onSelect(t))}
                    className="font-medium"
                  >
                    <span className="truncate">{t.cabinet}</span>
                    <Badge variant="secondary" className="ml-auto font-mono">
                      {t.devices.length}
                    </Badge>
                  </SidebarMenuButton>
                  {t.devices.length > 0 && (
                    <SidebarMenuSub>
                      {t.devices.map((d) => {
                        const review = isReview(d, p.threshold);
                        const Icon = review ? CircleAlert : CircleCheck;
                        return (
                          <SidebarMenuSubItem key={d.device_id}>
                            <SidebarMenuSubButton asChild isActive={selectedKey === d.device_id}>
                              <button
                                type="button"
                                data-key={d.device_id}
                                aria-current={selectedKey === d.device_id ? "true" : undefined}
                                aria-label={`${deviceLabel(d)}, ${review ? "needs review" : "OK"}`}
                                onClick={() => pick(() => p.onSelect(t, d))}
                                className="w-full text-left"
                              >
                                <span className={review ? "text-review" : "text-ok"}>
                                  <Icon aria-hidden="true" className="size-4" />
                                </span>
                                <span>{deviceLabel(d)}</span>
                              </button>
                            </SidebarMenuSubButton>
                          </SidebarMenuSubItem>
                        );
                      })}
                    </SidebarMenuSub>
                  )}
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </Section>
        </nav>
      </SidebarContent>
    </Sidebar>
  );
}
