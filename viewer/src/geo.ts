import { Vector3 } from "three";
import type { Point3 } from "./types";

export const CAMERA_HEIGHT = 1.44;

export const toThree = (p: Point3 | readonly number[]) =>
  Array.isArray(p) ? new Vector3(p[0], p[2], -p[1]) : new Vector3((p as Point3).x, (p as Point3).z, -(p as Point3).y);

export const fromThree = (v: Vector3): Point3 => ({ x: v.x, y: -v.z, z: v.y });

export function panoPixel(threeDir: Vector3, width: number, height: number) {
  const d = fromThree(threeDir.clone().normalize());
  const lon = Math.atan2(d.y, d.x);
  const lat = Math.asin(Math.max(-1, Math.min(1, d.z)));
  const u = (((Math.PI - lon) / (2 * Math.PI)) * width) % width;
  return { u, v: ((Math.PI / 2 - lat) / Math.PI) * height };
}

export function panoDir(u: number, v: number, width: number, height: number) {
  const lon = Math.PI - (u / width) * 2 * Math.PI;
  const lat = Math.PI / 2 - (v / height) * Math.PI;
  return toThree([Math.cos(lat) * Math.cos(lon), Math.cos(lat) * Math.sin(lon), Math.sin(lat)]);
}
