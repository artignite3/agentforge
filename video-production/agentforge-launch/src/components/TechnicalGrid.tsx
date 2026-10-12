import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C, F } from "../styles/designTokens";
import { ease, key } from "../utils/motion";
import { coreOutline } from "../utils/coreOutline";
export const TechnicalGrid: React.FC = () => {
  const f = useCurrentFrame();
  const strength = key(
    f,
    [0, 90, 210, 450, 780, 1110, 1350],
    [0.22, 0.4, 0.16, 0.22, 0.13, 0.16, 0.1],
  );
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg width="1920" height="1080" style={{ opacity: strength }}>
        <defs>
          <pattern
            id="grid"
            width="96"
            height="96"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 96 0 L 0 0 0 96"
              fill="none"
              stroke="#536075"
              strokeWidth=".7"
            />
          </pattern>
          <radialGradient id="grid-mask">
            <stop offset="0" stopColor="white" />
            <stop offset="1" stopColor="black" />
          </radialGradient>
          <mask id="gm">
            <ellipse
              cx="1080"
              cy="550"
              rx="1250"
              ry="650"
              fill="url(#grid-mask)"
            />
          </mask>
          <mask
            id="opening-grid-clearance"
            maskUnits="userSpaceOnUse"
            x="0"
            y="0"
            width="1920"
            height="1080"
          >
            <rect width="1920" height="1080" fill="white" />
            {f < 210 && <polygon points={coreOutline(f)} fill="black" />}
          </mask>
        </defs>
        <g mask="url(#opening-grid-clearance)">
          <rect width="1920" height="1080" fill="url(#grid)" mask="url(#gm)" />
          {Array.from({ length: 12 }, (_, i) => (
            <path
              key={i}
              d={`M ${96 + i * 144} 0 V 1080`}
              stroke={C.copper}
              strokeWidth=".5"
              strokeDasharray="1080"
              strokeDashoffset={1080 * (1 - ease(f, i * 3, 60 + i * 3))}
              opacity=".35"
            />
          ))}
        </g>
      </svg>
      <div
        style={{
          position: "absolute",
          left: 64,
          top: 44,
          fontFamily: F.mono,
          fontSize: 17,
          letterSpacing: ".15em",
          color: "#788391",
        }}
      >
        AGENTFORGE / EXECUTION SYSTEMS
      </div>
      <div
        style={{
          position: "absolute",
          right: 64,
          top: 44,
          fontFamily: F.mono,
          fontSize: 17,
          letterSpacing: ".15em",
          color: "#788391",
        }}
      >
        DURABLE BY DESIGN
      </div>
      <svg width="1920" height="1080" style={{ position: "absolute" }}>
        {[
          [64, 90],
          [1856, 90],
          [64, 982],
          [1856, 982],
        ].map(([x, y], i) => (
          <path
            key={i}
            d={`M ${x - 8} ${y} H ${x + 8} M ${x} ${y - 8} V ${y + 8}`}
            stroke="#526074"
            strokeWidth="1"
          />
        ))}
      </svg>
    </AbsoluteFill>
  );
};
