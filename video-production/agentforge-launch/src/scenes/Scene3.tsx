import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C, F } from "../styles/designTokens";
import { ease, gate } from "../utils/motion";
import {
  MaskReveal,
  Micro,
  Rule,
  StaggeredWords,
  TrackingText,
} from "../components/KineticText";
import { modules } from "../components/CheckpointWorld";
import { projectPoint } from "../components/CameraRig";
export const Scene3: React.FC = () => {
  const local = useCurrentFrame(),
    f = local + 450;
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 110, top: 140 }}>
        <Micro color={C.copper}>03 / THE EXECUTION CONTRACT</Micro>
        {local < 108 ? (
          <MaskReveal
            text="QUEUE + STATE"
            start={3}
            end={108}
            size={96}
            style={{ marginTop: 17 }}
          />
        ) : local < 177 ? (
          <StaggeredWords
            text="COMMITTED TOGETHER"
            start={104}
            end={178}
            size={87}
            style={{ marginTop: 17 }}
          />
        ) : local < 222 ? (
          <TrackingText
            text="FENCED COMMITS"
            start={175}
            end={224}
            size={92}
            width={1680}
            style={{ marginTop: 17 }}
          />
        ) : local < 267 ? (
          <MaskReveal
            text="RECORDED ROUTING"
            start={219}
            end={269}
            size={91}
            style={{ marginTop: 17 }}
          />
        ) : (
          <StaggeredWords
            text="ISOLATED TOOLS"
            start={264}
            end={329}
            size={96}
            style={{ marginTop: 17 }}
          />
        )}
        <Rule start={5} width={1690} />
      </div>
      {modules.map((m) => {
        const p = projectPoint([m.point[0], m.point[1] - 0.35, m.point[2]], f);
        const reveal =
          ease(f, m.start + 8, m.start + 30) * (1 - ease(f, 762, 780));
        return (
          <div
            key={m.id}
            style={{
              position: "absolute",
              left: p.x - 135,
              top: p.y + 48,
              width: 270,
              textAlign: "center",
              opacity: reveal,
              transform: `translateY(${(1 - reveal) * 18}px)`,
              background:
                "linear-gradient(180deg,#0B0F1700,#0B0F17AA 20%,#0B0F1700)",
            }}
          >
            <div
              style={{
                fontFamily: F.mono,
                fontSize: m.id === "gateway" ? 20 : 22,
                color: C.ink,
                letterSpacing: ".055em",
                whiteSpace: "nowrap",
              }}
            >
              {m.label}
            </div>
            <div
              style={{
                fontFamily: F.mono,
                fontSize: 14,
                color: C.muted,
                letterSpacing: ".03em",
                marginTop: 7,
              }}
            >
              {m.detail}
            </div>
          </div>
        );
      })}
      <div
        style={{
          position: "absolute",
          left: 115,
          bottom: 146,
          opacity: 1 - ease(f, 762, 780),
        }}
      >
        <Micro color={C.copper}>
          {local < 100
            ? "ONE DURABLE STORE"
            : local < 172
              ? "STEP + CHECKPOINT + EVENT / ONE TRANSACTION"
              : local < 221
                ? "STALE LEASES CANNOT COMMIT"
                : local < 267
                  ? "COST + FAILURE HISTORY / EXPLICIT RULES"
                  : "NO NETWORK / NO HOST MOUNTS / RESOURCE LIMITS"}
        </Micro>
      </div>
      <div
        style={{
          position: "absolute",
          right: 112,
          bottom: 145,
          opacity: gate(f, 620, 763, 12, 10),
          fontFamily: F.mono,
          fontSize: 18,
          color: C.muted,
        }}
      >
        AT-LEAST-ONCE EXECUTION · FENCED COMMITS
      </div>
    </AbsoluteFill>
  );
};
