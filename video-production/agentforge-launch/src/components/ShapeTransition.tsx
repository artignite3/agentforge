import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C } from "../styles/designTokens";
import { move } from "../utils/motion";
export const ShapeTransition: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {[450, 780, 1110].map((boundary, i) => {
        if (f < boundary - 18 || f > boundary + 18) return null;
        const p = move(f, boundary - 18, boundary + 18);
        const x = -1100 + p * 4100;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: -200,
              width: 650,
              height: 1480,
              background: `linear-gradient(90deg, transparent 0%, ${C.copper}08 23%, #0B0F17 42%, #0B0F17 75%, ${C.copper}30 76%, transparent 79%)`,
              transform: "rotate(-20deg)",
              filter: `blur(${Math.sin(p * Math.PI) * 5}px)`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
