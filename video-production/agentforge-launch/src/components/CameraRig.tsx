import React, { useLayoutEffect } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { key, move } from "../utils/motion";
export type V3 = [number, number, number];
export function cameraPose(f: number): { eye: V3; target: V3 } {
  if (f < 480) {
    const q = Math.min(f, 420);
    const old: V3 = [
      key(q, [0, 90, 210, 330, 405, 450], [0, 0.6, 1.2, -0.1, 2.6, 3.4]),
      key(q, [0, 210, 330, 450], [0.3, 1.1, 1.6, 0.2]),
      key(q, [0, 90, 210, 330, 405, 450], [19, 17.8, 16, 16.7, 14, 7.8]),
    ];
    const p = move(f, 420, 480);
    const destination: V3 = [1.5, 2.1, 19.7];
    return {
      eye: old.map((x, i) => x * (1 - p) + destination[i] * p) as V3,
      target: [2.8 * (1 - p) + 1.2 * p, 0.15 * (1 - p) - 0.3 * p, 0],
    };
  }
  if (f < 798)
    return {
      eye: [
        key(f, [480, 600, 716, 798], [1.5, 2.8, 2, 0]),
        key(f, [480, 600, 716, 798], [2.1, 1.4, 1.1, 0]),
        key(f, [480, 600, 716, 798], [19.7, 18.3, 16, 19]),
      ],
      target: [key(f, [716, 798], [1.2, 0]), key(f, [716, 798], [-0.3, 0]), 0],
    };
  if (f < 1094) return { eye: [0, 0, 19], target: [0, 0, 0] };
  return {
    eye: [
      key(f, [1094, 1140, 1206, 1350], [0, 0.6, 0, 0]),
      key(f, [1094, 1140, 1206, 1350], [0, 1.8, 0.1, 0]),
      key(f, [1094, 1140, 1206, 1350], [19, 15.7, 21, 22]),
    ],
    target: [0, 0, 0],
  };
}
export const CameraRig: React.FC<{ frame: number }> = ({ frame }) => {
  const { camera } = useThree();
  useLayoutEffect(() => {
    const p = cameraPose(frame);
    camera.position.set(...p.eye);
    camera.lookAt(...p.target);
    camera.updateMatrixWorld();
  }, [frame, camera]);
  return null;
};
export function projectPoint(point: V3, frame: number) {
  const camera = new THREE.PerspectiveCamera(40, 1920 / 1080, 0.1, 100);
  const p = cameraPose(frame);
  camera.position.set(...p.eye);
  camera.lookAt(...p.target);
  camera.updateMatrixWorld();
  const v = new THREE.Vector3(...point).project(camera);
  return { x: (v.x + 1) * 960, y: (1 - v.y) * 540 };
}
