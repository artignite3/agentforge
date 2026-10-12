import { key } from "./motion";
import type { V3 } from "../components/CameraRig";

// Share the transform between the opening object and its data-field occlusion.
export function corePose(f: number): {
  split: number;
  scale: number;
  center: V3;
  rotation: V3;
} {
  const outro = f >= 1094;
  const spin = outro
    ? key(f, [1110, 1170, 1236], [-0.35, 0.15, 0])
    : key(f, [0, 100, 210, 330, 450], [0.3, 0.45, -0.35, -0.12, 0.05]);
  const split = outro
    ? key(f, [1110, 1170, 1215], [0.75, 0.35, 0.24])
    : key(f, [0, 90, 180, 260, 380, 450], [0.72, 0.72, 0.6, 0.34, 0.34, 0.25]);
  const scale = outro
    ? key(f, [1094, 1110, 1170, 1236], [0.002, 0.65, 0.44, 0.35])
    : key(f, [420, 480], [1, 0.32]);
  const center: V3 = outro
    ? [0, key(f, [1094, 1206], [0, 1.8]), 0]
    : [key(f, [420, 480], [3.4, -0.5]), key(f, [420, 480], [0.15, 0.65]), 0];
  const yrot = outro
    ? key(f, [1110, 1236], [-0.35, 0])
    : key(f, [0, 100, 210, 330, 450], [-0.5, -0.32, 0.4, 0.12, 0]);
  return {
    split,
    scale,
    center,
    rotation: [
      spin,
      yrot,
      outro ? 0 : key(f, [0, 210, 330, 450], [-0.22, 0.13, 0.04, 0]),
    ],
  };
}
