import type { Vector3 } from "three";
import { fromThree } from "./geo";

const ROWS = 1800;
const COLS = 3600;
const STEP = (0.1 * Math.PI) / 180;
const HORIZON = 900;

function half(h: number) {
  const e = (h >> 10) & 0x1f;
  const m = h & 0x3ff;
  const v = e === 0 ? m * 2 ** -24 : e === 31 ? Infinity : (1 + m / 1024) * 2 ** (e - 15);
  return h & 0x8000 ? -v : v;
}

async function npzArray(buf: ArrayBuffer) {
  const dv = new DataView(buf);
  if (dv.getUint32(0, true) !== 0x04034b50) throw new Error("not a zip file");
  const method = dv.getUint16(8, true);
  let size = dv.getUint32(18, true);
  const nameLen = dv.getUint16(26, true);
  const extraLen = dv.getUint16(28, true);
  const start = 30 + nameLen + extraLen;
  if (size === 0xffffffff) {
    for (let p = 30 + nameLen; p < start; p += 4 + dv.getUint16(p + 2, true)) {
      if (dv.getUint16(p, true) === 1) size = Number(dv.getBigUint64(p + 12, true));
    }
  }
  let data = new Uint8Array(buf, start, size);
  if (method === 8) {
    const stream = new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    data = new Uint8Array(await new Response(stream).arrayBuffer());
  }
  const ndv = new DataView(data.buffer, data.byteOffset);
  const major = data[6];
  const headerLen = major === 1 ? ndv.getUint16(8, true) : ndv.getUint32(8, true);
  const offset = (major === 1 ? 10 : 12) + headerLen;
  const header = new TextDecoder().decode(data.subarray(major === 1 ? 10 : 12, offset));
  if (!header.includes("'<f2'") || !header.includes(`(${ROWS}, ${COLS})`)) throw new Error(`unexpected depth grid ${header}`);
  return new Uint16Array(data.buffer.slice(data.byteOffset + offset, data.byteOffset + offset + ROWS * COLS * 2));
}

export class DepthGrid {
  private constructor(private readonly grid: Uint16Array, private readonly rotation: number[][]) {}

  static async load(url: string, rotation: number[][]) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return new DepthGrid(await npzArray(await res.arrayBuffer()), rotation);
  }

  /** Largest range in a 3 x 3 cell window around a world direction (three frame). 0 when unknown. */
  range(threeDir: Vector3) {
    const d = fromThree(threeDir.clone().normalize());
    const R = this.rotation;
    const lx = R[0][0] * d.x + R[1][0] * d.y + R[2][0] * d.z;
    const ly = R[0][1] * d.x + R[1][1] * d.y + R[2][1] * d.z;
    const lz = R[0][2] * d.x + R[1][2] * d.y + R[2][2] * d.z;
    const el = Math.asin(Math.max(-1, Math.min(1, lz)));
    let az = Math.atan2(ly, lx);
    if (az < 0) az += 2 * Math.PI;
    const row = Math.round(el / STEP + HORIZON);
    const col = Math.floor(az / STEP);
    let best = 0;
    for (let dr = -1; dr <= 1; dr++) {
      const r = Math.max(0, Math.min(ROWS - 1, row + dr));
      for (let dc = -1; dc <= 1; dc++) best = Math.max(best, half(this.grid[r * COLS + ((col + dc + COLS) % COLS)]));
    }
    return best;
  }
}
