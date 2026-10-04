import type { ComponentType } from "react";
import { M01Title } from "./scenes/m01-title";
import { M02Problem } from "./scenes/m02-problem";
import { M03Seventy } from "./scenes/m03-seventy";
import { M04Results } from "./scenes/m04-results";
import { M05NoPhotos } from "./scenes/m05-no-photos";
import { M06Counter } from "./scenes/m06-counter";
import { M07OneCamera } from "./scenes/m07-one-camera";
import { M08CustomModel } from "./scenes/m08-custom-model";
import { M09Gpus } from "./scenes/m09-gpus";
import { M10RunTable } from "./scenes/m10-run-table";
import { M11HeldOut } from "./scenes/m11-held-out";
import { M12DarkRecall } from "./scenes/m12-dark-recall";
import { M13Tiles } from "./scenes/m13-tiles";
import { M14Ray } from "./scenes/m14-ray";
import { M15Production } from "./scenes/m15-production";
import { M16NextDevice } from "./scenes/m16-next-device";
import { M17Close } from "./scenes/m17-close";

export const scenes: { id: string; component: ComponentType<{ overlay?: boolean }>; seconds: number; overlay?: boolean }[] = [
  { id: "m01-title", component: M01Title, seconds: 8, overlay: false },
  { id: "m02-problem", component: M02Problem, seconds: 10 },
  { id: "m03-seventy", component: M03Seventy, seconds: 5 },
  { id: "m04-results", component: M04Results, seconds: 6, overlay: false },
  { id: "m05-no-photos", component: M05NoPhotos, seconds: 2 },
  { id: "m06-counter", component: M06Counter, seconds: 6 },
  { id: "m07-one-camera", component: M07OneCamera, seconds: 7 },
  { id: "m08-custom-model", component: M08CustomModel, seconds: 14 },
  { id: "m09-gpus", component: M09Gpus, seconds: 6 },
  { id: "m10-run-table", component: M10RunTable, seconds: 16 },
  { id: "m11-held-out", component: M11HeldOut, seconds: 12 },
  { id: "m12-dark-recall", component: M12DarkRecall, seconds: 6, overlay: false },
  { id: "m13-tiles", component: M13Tiles, seconds: 8 },
  { id: "m14-ray", component: M14Ray, seconds: 8 },
  { id: "m15-production", component: M15Production, seconds: 5 },
  { id: "m16-next-device", component: M16NextDevice, seconds: 8 },
  { id: "m17-close", component: M17Close, seconds: 10 },
];
