import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C, F } from "../styles/designTokens";
import { ease } from "../utils/motion";
import {
  MaskReveal,
  Micro,
  Rule,
  TrackingText,
} from "../components/KineticText";
export const Scene2: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 110, top: 148 }}>
        <MaskReveal
          text="MEET"
          start={3}
          end={194}
          size={52}
          color={C.copper}
        />
        <TrackingText
          text="AGENTFORGE"
          start={24}
          end={233}
          size={158}
          width={1700}
          style={{ marginTop: 22 }}
        />
        <Rule start={30} width={1620} />
      </div>
      <div style={{ position: "absolute", left: 115, top: 496, width: 640 }}>
        <MaskReveal text="Durable execution." start={54} end={209} size={52} />
        <MaskReveal
          text="For repository agents."
          start={69}
          end={209}
          size={45}
          color={C.muted}
          style={{ marginTop: 12 }}
        />
      </div>
      <div
        style={{
          position: "absolute",
          left: 115,
          bottom: 182,
          opacity: ease(f, 115, 133) * (1 - ease(f, 215, 238)),
        }}
      >
        <Micro color={C.copper}>RESUME / LAST COMMITTED CHECKPOINT</Micro>
        <div
          style={{
            fontFamily: F.mono,
            fontSize: 20,
            color: C.muted,
            marginTop: 14,
            letterSpacing: ".045em",
          }}
        >
          AFTER LEASE EXPIRY · TIME CONDENSED
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          right: 110,
          bottom: 181,
          opacity: ease(f, 105, 127) * (1 - ease(f, 213, 239)),
          display: "flex",
          alignItems: "center",
          gap: 18,
        }}
      >
        <div style={{ width: 8, height: 8, background: C.cyan }} />
        <Micro color={C.ink}>NEW LEASE / SAME RUN</Micro>
      </div>
    </AbsoluteFill>
  );
};
