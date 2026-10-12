import React, { useMemo, useEffect } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import * as THREE from "three";
import { C } from "../styles/designTokens";
import { ease, move } from "../utils/motion";
import { CameraRig, V3 } from "./CameraRig";
import { corePose } from "../utils/corePose";
import {
  DataFieldMaterial,
  OpeningObjectOcclusion,
} from "./OpeningObjectOcclusion";

const ringShape = () => {
  const shape = new THREE.Shape();
  shape.moveTo(-3.3, -2);
  shape.lineTo(2.95, -2);
  shape.quadraticCurveTo(3.3, -2, 3.3, -1.65);
  shape.lineTo(3.3, 1.65);
  shape.quadraticCurveTo(3.3, 2, 2.95, 2);
  shape.lineTo(-2.95, 2);
  shape.quadraticCurveTo(-3.3, 2, -3.3, 1.65);
  shape.lineTo(-3.3, -1.65);
  shape.quadraticCurveTo(-3.3, -2, -2.95, -2);
  const hole = new THREE.Path();
  hole.moveTo(-2.65, -1.37);
  hole.lineTo(-2.65, 1.37);
  hole.lineTo(2.65, 1.37);
  hole.lineTo(2.65, -1.37);
  hole.closePath();
  shape.holes.push(hole);
  return shape;
};
const ringGeometry = new THREE.ExtrudeGeometry(ringShape(), {
  depth: 0.2,
  bevelEnabled: true,
  bevelThickness: 0.06,
  bevelSize: 0.06,
  bevelSegments: 2,
  steps: 1,
});
const ringEdges = new THREE.EdgesGeometry(ringGeometry, 28);

const Tube: React.FC<{
  points: V3[];
  color?: string;
  radius?: number;
  opacity?: number;
}> = ({ points, color = C.copper, radius = 0.013, opacity = 1 }) => {
  const geometry = useMemo(
    () =>
      new THREE.TubeGeometry(
        new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p))),
        24,
        radius,
        4,
        false,
      ),
    [JSON.stringify(points), radius],
  );
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <mesh geometry={geometry}>
      <DataFieldMaterial color={color} opacity={opacity} />
    </mesh>
  );
};

function Core({ f }: { f: number }) {
  const outro = f >= 1094;
  const { split, scale, center, rotation } = corePose(f);
  return (
    <group position={center} rotation={rotation} scale={scale}>
      {Array.from({ length: 4 }, (_, i) => (
        <group key={i} position={[0, 0, (i - 1.5) * split]}>
          <mesh geometry={ringGeometry}>
            <meshStandardMaterial
              color={i === 3 ? "#b4866d" : "#30414b"}
              metalness={0.62}
              roughness={0.32}
              transparent
              opacity={outro ? 1 : 1 - ease(f, 468, 487)}
            />
          </mesh>
          <lineSegments geometry={ringEdges}>
            <lineBasicMaterial
              color={i === 3 ? C.copper : "#73919d"}
              transparent
              opacity={
                (i === 3 ? 0.8 : 0.45) * (outro ? 1 : 1 - ease(f, 468, 487))
              }
            />
          </lineSegments>
          {[0, 1, 2, 3, 4, 5].map((j) => (
            <mesh key={j} position={[-2.8 + j * 1.05, -1.72, 0.26]}>
              <boxGeometry args={[0.4, 0.055, 0.02]} />
              <meshBasicMaterial
                color={i < 3 ? C.cyan : C.copper}
                transparent
                opacity={0.65}
              />
            </mesh>
          ))}
        </group>
      ))}
      <Tube
        points={[
          [-3.5, -2.1, 1.2],
          [-0.2, -2.1, 1.2],
          [1.6, -2.1, 1.2],
          [3.5, -2.1, 1.2],
        ]}
        color={C.copper}
        radius={0.021}
      />
    </group>
  );
}

function Tangle({ f }: { f: number }) {
  const resolve = move(f, 175, 265);
  const crash = ease(f, 78, 91);
  const fade = 1 - ease(f, 230, 278);
  if (!fade) return null;
  return (
    <group>
      {Array.from({ length: 32 }, (_, i) => {
        const raw: V3[] = Array.from({ length: 5 }, (_, j) => [
          -8.7 + j * 4.6 + Math.sin(i * 2.7 + j) * 1.2,
          Math.sin(i * 1.73 + j * 1.6) * 4.2,
          Math.cos(i * 1.27 + j) * 3,
        ]);
        const aligned: V3[] = Array.from({ length: 5 }, (_, j) => [
          -0.1 + j * 1.74,
          ((i % 4) - 1.5) * 0.7,
          ((Math.floor(i / 4) % 4) - 1.5) * 0.34,
        ]);
        const points = raw.map(
          (p, j) =>
            p.map((x, k) => x * (1 - resolve) + aligned[j][k] * resolve) as V3,
        );
        const active = i % 5 === 0;
        const pulse = (f * 0.005 + i * 0.071) % 1;
        const curve = new THREE.CatmullRomCurve3(
          points.map((p) => new THREE.Vector3(...p)),
        );
        const node = curve.getPoint(pulse);
        return (
          <group key={i}>
            <Tube
              points={points}
              color={active ? C.copper : "#3a5366"}
              radius={active ? 0.022 : 0.008}
              opacity={fade * (active ? 0.7 : 0.36)}
            />
            {active && (
              <mesh position={node} scale={0.065 * (1 - crash * 0.6)}>
                <sphereGeometry args={[1, 8, 8]} />
                <DataFieldMaterial
                  color={i === 5 && crash > 0.2 ? C.red : C.cyan}
                  opacity={fade}
                />
              </mesh>
            )}
          </group>
        );
      })}
    </group>
  );
}

export const modules: {
  id: string;
  point: V3;
  label: string;
  detail: string;
  start: number;
}[] = [
  {
    id: "api",
    point: [-4, 1, 0],
    label: "FASTAPI",
    detail: "CONTROL PLANE",
    start: 450,
  },
  {
    id: "pg",
    point: [-0.5, 1, 0],
    label: "POSTGRESQL",
    detail: "QUEUE + STATE",
    start: 464,
  },
  {
    id: "worker",
    point: [3, 1, 0],
    label: "ASYNC WORKER",
    detail: "FENCED LEASE",
    start: 470,
  },
  {
    id: "redis",
    point: [-4, -1.6, 0],
    label: "REDIS",
    detail: "API RATE LIMITS",
    start: 474,
  },
  {
    id: "router",
    point: [6, -0.1, 0],
    label: "ROUTER",
    detail: "RECORDED RULES",
    start: 658,
  },
  {
    id: "openai",
    point: [8, 1.2, 0],
    label: "OPENAI",
    detail: "ADAPTER",
    start: 666,
  },
  {
    id: "gemini",
    point: [8, -1.8, 0],
    label: "GEMINI",
    detail: "ADAPTER",
    start: 675,
  },
  {
    id: "gateway",
    point: [2.7, -2.1, 0],
    label: "PRIVATE GATEWAY",
    detail: "BOUNDED REQUEST",
    start: 708,
  },
  {
    id: "docker",
    point: [-0.5, -2.6, 0],
    label: "DOCKER TOOLS",
    detail: "DISPOSABLE / NON-ROOT",
    start: 718,
  },
];
function Architecture({ f }: { f: number }) {
  const paths: { from: string; to: string; start: number }[] = [
    { from: "api", to: "pg", start: 462 },
    { from: "pg", to: "worker", start: 481 },
    { from: "api", to: "redis", start: 480 },
    { from: "worker", to: "router", start: 665 },
    { from: "router", to: "openai", start: 675 },
    { from: "router", to: "gemini", start: 687 },
    { from: "worker", to: "gateway", start: 714 },
    { from: "gateway", to: "docker", start: 726 },
    { from: "docker", to: "pg", start: 740 },
  ];
  return (
    <group position={[0, -0.35, 0]}>
      {modules.map((m) => {
        const p = ease(f, m.start, m.start + 26);
        return (
          <group
            key={m.id}
            position={[m.point[0], m.point[1] + (1 - p) * 1.2, m.point[2]]}
            scale={Math.max(0.001, p)}
          >
            {m.id === "pg" ? (
              <group rotation={[0.3, 0, 0]}>
                {[0, 1, 2].map((i) => (
                  <group key={i} position={[0, 0, i * 0.24]} scale={0.32}>
                    <mesh geometry={ringGeometry}>
                      <meshStandardMaterial
                        color={i === 2 ? C.copper : "#394c5e"}
                        roughness={0.38}
                        metalness={0.35}
                      />
                    </mesh>
                    <lineSegments geometry={ringEdges}>
                      <lineBasicMaterial color={C.copper} />
                    </lineSegments>
                  </group>
                ))}
              </group>
            ) : m.id === "docker" ? (
              <group scale={0.27} rotation={[0.18, -0.25, 0]}>
                {[0, 1].map((i) => (
                  <group key={i} position={[0, 0, i * 1.2]}>
                    <mesh geometry={ringGeometry}>
                      <meshStandardMaterial
                        color="#325463"
                        metalness={0.4}
                        roughness={0.4}
                      />
                    </mesh>
                    <lineSegments geometry={ringEdges}>
                      <lineBasicMaterial color={C.cyan} />
                    </lineSegments>
                  </group>
                ))}
              </group>
            ) : (
              <group>
                <mesh>
                  <boxGeometry
                    args={[m.id === "worker" ? 1.8 : 1.45, 0.82, 0.28]}
                  />
                  <meshStandardMaterial
                    color={m.id === "worker" ? "#455469" : "#293947"}
                    metalness={0.38}
                    roughness={0.35}
                  />
                </mesh>
                <mesh position={[0, 0.36, 0.16]}>
                  <boxGeometry
                    args={[m.id === "worker" ? 1.78 : 1.42, 0.035, 0.025]}
                  />
                  <meshBasicMaterial
                    color={m.id === "router" ? C.indigo : C.copper}
                  />
                </mesh>
                {[0, 1, 2].map((j) => (
                  <mesh key={j} position={[-0.4 + j * 0.23, -0.13, 0.17]}>
                    <boxGeometry args={[0.12, 0.026, 0.02]} />
                    <meshBasicMaterial color={C.cyan} />
                  </mesh>
                ))}
              </group>
            )}
          </group>
        );
      })}
      {paths.map(({ from, to, start }, i) => {
        const a = modules.find((m) => m.id === from)!.point,
          b = modules.find((m) => m.id === to)!.point;
        const p = ease(f, start, start + 25);
        const points: V3[] = [
          a,
          [a[0], a[1], 0.45],
          [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.6],
          [b[0], b[1], 0.45],
          b,
        ];
        const curve = new THREE.CatmullRomCurve3(
          points.map((v) => new THREE.Vector3(...v)),
        );
        const node = curve.getPoint(
          ((f - start) * 0.014 + i * 0.14) % 1 < 0
            ? 0
            : ((f - start) * 0.014 + i * 0.14) % 1,
        );
        return (
          <group key={i}>
            <Tube
              points={points}
              color={i > 5 ? C.cyan : C.copper}
              opacity={p * 0.55}
              radius={0.015}
            />
            {p > 0.1 && (
              <mesh position={node} scale={0.055}>
                <sphereGeometry args={[1, 8, 8]} />
                <meshBasicMaterial color={i > 5 ? C.cyan : C.copper} />
              </mesh>
            )}
          </group>
        );
      })}
      {f > 548 && f < 630 && (
        <group position={[-0.5, 1, 1.3]}>
          {[0, 1, 2].map((i) => (
            <mesh
              key={i}
              position={[0, (i - 1) * move(f, 548, 575, 0.16, 0.6), 0]}
            >
              <boxGeometry args={[2.75, 0.035, 0.06]} />
              <meshBasicMaterial color={i === 1 ? C.copper : C.cyan} />
            </mesh>
          ))}
        </group>
      )}
      {f >= 618 && (
        <group position={[1.1, 1, 0.55]}>
          {[-1, 1].map((side, i) => (
            <mesh
              key={i}
              position={[0, side * 0.85, 0]}
              scale={[1, ease(f, 618, 642), 1]}
            >
              <boxGeometry args={[0.045, 1.4, 0.14]} />
              <meshStandardMaterial color={C.copper} roughness={0.4} />
            </mesh>
          ))}
        </group>
      )}
    </group>
  );
}

export const CheckpointWorld: React.FC = () => {
  const f = useCurrentFrame(),
    { width, height } = useVideoConfig();
  if (f >= 798 && f < 1094) return null;
  return (
    <AbsoluteFill>
      <ThreeCanvas
        width={width}
        height={height}
        dpr={0.75}
        gl={{ alpha: true, antialias: true, stencil: true }}
        camera={{ fov: 40, near: 0.1, far: 100, position: [0, 0, 19] }}
        style={{ background: "transparent" }}
      >
        <CameraRig frame={f} />
        <ambientLight intensity={1.15} />
        <directionalLight
          position={[-4, 7, 9]}
          intensity={3.2}
          color="#d5e6fa"
        />
        <pointLight position={[6, 3, 5]} intensity={70} color={C.copper} />
        <pointLight position={[-5, -3, 4]} intensity={45} color="#3f98bc" />
        {f < 278 && (
          <OpeningObjectOcclusion>
            <Tangle f={f} />
          </OpeningObjectOcclusion>
        )}{" "}
        {(f < 487 || f >= 1094) && <Core f={f} />}{" "}
        {f >= 450 && f < 798 && (
          <group scale={[1, 1 - ease(f, 760, 798) * 0.93, 1]}>
            <Architecture f={f} />
          </group>
        )}
      </ThreeCanvas>
    </AbsoluteFill>
  );
};
