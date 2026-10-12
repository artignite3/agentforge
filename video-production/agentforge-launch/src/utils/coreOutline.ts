import * as THREE from "three";
import { cameraPose } from "../components/CameraRig";
import { corePose } from "./corePose";
type Point = [number, number];

export function coreOutline(f: number, width = 1920, height = 1080): string {
  const pose = corePose(f),
    view = cameraPose(f);
  const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
  camera.position.set(...view.eye);
  camera.lookAt(...view.target);
  camera.updateMatrixWorld();
  const matrix = new THREE.Matrix4().compose(
    new THREE.Vector3(...pose.center),
    new THREE.Quaternion().setFromEuler(new THREE.Euler(...pose.rotation)),
    new THREE.Vector3(pose.scale, pose.scale, pose.scale),
  );
  const points: Point[] = [];
  for (const x of [-3.38, 3.38])
    for (const y of [-2.08, 2.08])
      for (const z of [-1.5 * pose.split - 0.08, 1.5 * pose.split + 0.28]) {
        const p = new THREE.Vector3(x, y, z)
          .applyMatrix4(matrix)
          .project(camera);
        points.push([((p.x + 1) * width) / 2, ((1 - p.y) * height) / 2]);
      }
  const ordered = points.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (a: Point, b: Point, c: Point) =>
    (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const lower: Point[] = [],
    upper: Point[] = [];
  for (const p of ordered) {
    while (
      lower.length > 1 &&
      cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0
    )
      lower.pop();
    lower.push(p);
  }
  for (const p of [...ordered].reverse()) {
    while (
      upper.length > 1 &&
      cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0
    )
      upper.pop();
    upper.push(p);
  }
  lower.pop();
  upper.pop();
  return [...lower, ...upper].map(([x, y]) => `${x},${y}`).join(" ");
}
