import { useEffect, useRef, useState, type RefObject } from "react";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import { Player, type Mode, type PlayerEvents } from "@/player";
import type { Manifest } from "@/types";

interface StageProps {
  manifest: Manifest;
  events: RefObject<PlayerEvents>;
  onReady(player: Player | null): void;
  status: string;
  mode: Mode;
}

export function Stage({ manifest, events, onReady, status, mode }: StageProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<Player | null>(null);
  const [cut, setCut] = useState(2.6);

  useEffect(() => {
    const forward: PlayerEvents = {
      select: (t, d) => events.current.select(t, d),
      sweep: (s) => events.current.sweep(s),
      mode: (m) => events.current.mode(m),
      status: (text, ms) => events.current.status(text, ms),
      escape: (target) => events.current.escape(target),
    };
    const player = new Player(canvasRef.current!, stageRef.current!, overlayRef.current!, manifest, forward);
    playerRef.current = player;
    onReady(player);
    return () => {
      onReady(null);
      playerRef.current = null;
      player.dispose();
    };
  }, [manifest, events, onReady]);

  return (
    <div ref={stageRef} className="stage relative min-h-0 min-w-0 flex-1 overflow-hidden bg-stage max-md:min-h-[60vh]">
      <canvas
        ref={canvasRef}
        id="stage-canvas"
        tabIndex={0}
        role="application"
        aria-roledescription="3D view"
        className="block size-full focus-visible:outline-3 focus-visible:-outline-offset-4 focus-visible:outline-ring"
      />
      <div ref={overlayRef} id="overlay" className="overlay pointer-events-none absolute inset-0 overflow-hidden" />
      {mode === "dollhouse" && manifest.cloud && (
        <div className="absolute top-3 right-3 flex w-56 flex-col gap-2 rounded-lg border bg-scrim p-3 shadow-md">
          <div className="flex items-center justify-between">
            <Label asChild>
              <span id="cut-label">Cut height (m)</span>
            </Label>
            <output htmlFor="cut-height" className="font-mono text-xs">
              {cut.toFixed(1)}
            </output>
          </div>
          <Slider
            id="cut-height"
            aria-labelledby="cut-label"
            min={0.5}
            max={5}
            step={0.1}
            value={[cut]}
            onValueChange={([v]) => {
              setCut(v);
              if (playerRef.current) playerRef.current.cut = v;
            }}
          />
        </div>
      )}
      <p
        role="status"
        aria-live="polite"
        className={cn(
          "absolute bottom-4 left-1/2 m-0 max-w-[min(90%,40rem)] -translate-x-1/2 rounded-lg border bg-scrim px-3.5 py-2 text-center shadow-md",
          !status && "hidden",
        )}
      >
        {status}
      </p>
    </div>
  );
}
