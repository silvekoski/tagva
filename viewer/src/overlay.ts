import { Vector3, type Camera, type PerspectiveCamera } from "three";

export interface Marker {
  el: HTMLElement;
  pos: Vector3;
  radius?: number;
  visible?: () => boolean;
  occluded?: () => boolean;
}

const FAR = 4.5;

const tmp = new Vector3();
const right = new Vector3();

export class Overlay {
  markers: Marker[] = [];

  constructor(readonly root: HTMLElement) {}

  set(markers: Marker[]) {
    this.root.replaceChildren(...markers.map((m) => m.el));
    this.markers = markers;
  }

  update(camera: Camera, width: number, height: number) {
    right.setFromMatrixColumn(camera.matrixWorld, 0);
    const fwd = new Vector3();
    camera.getWorldDirection(fwd);
    for (const m of this.markers) {
      const ahead = tmp.copy(m.pos).sub(camera.position).dot(fwd) > 0.05;
      tmp.copy(m.pos).project(camera);
      const x = (tmp.x * 0.5 + 0.5) * width;
      const y = (-tmp.y * 0.5 + 0.5) * height;
      const show = ahead && x > -40 && x < width + 40 && y > -40 && y < height + 40 && (m.visible?.() ?? true);
      if (m.el.hidden === show) m.el.hidden = !show;
      if (!show) continue;
      m.el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
      m.el.classList.toggle("far", m.pos.distanceTo(camera.position) > FAR);
      if (m.occluded) m.el.classList.toggle("occluded", m.occluded());
      if (m.radius) {
        tmp.copy(m.pos).addScaledVector(right, m.radius).project(camera);
        const r = Math.max(14, Math.abs((tmp.x * 0.5 + 0.5) * width - x));
        m.el.style.setProperty("--r", `${r.toFixed(1)}px`);
        m.el.style.setProperty("--ry", `${(r * flatten(camera as PerspectiveCamera, m.pos)).toFixed(1)}px`);
      }
    }
  }
}

function flatten(camera: PerspectiveCamera, pos: Vector3) {
  const d = tmp.copy(camera.position).sub(pos).normalize();
  return Math.max(0.25, Math.abs(d.y));
}
