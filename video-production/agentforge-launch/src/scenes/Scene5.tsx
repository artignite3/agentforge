import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C, F } from "../styles/designTokens";
import { ease, move } from "../utils/motion";
import { MaskReveal, Micro, TrackingText } from "../components/KineticText";
export const Scene5: React.FC = () => {
  const f = useCurrentFrame();
  const p = ease(f, 35, 90);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: 110,
          right: 110,
          top: 148,
          textAlign: "center",
          opacity: 1 - ease(f, 88, 112),
        }}
      >
        <Micro color={C.copper}>BUILD AGENTS FOR THE FAILURE PATH.</Micro>
      </div>
      <svg
        width="1920"
        height="1080"
        style={{ position: "absolute", pointerEvents: "none", opacity: p }}
      >
        <g
          transform={`translate(960 ${move(f, 35, 95, 300, 322)}) scale(${move(f, 35, 95, 1.3, 1)})`}
          stroke={C.copper}
          strokeWidth="4"
          fill="none"
          strokeLinejoin="round"
        >
          {[0, 1, 2].map((i) => (
            <path
              key={i}
              d={`M -62 ${-40 + i * 30} L 0 ${-69 + i * 30} L 62 ${-40 + i * 30} L 0 ${-11 + i * 30} Z`}
              style={{
                transform: `translateY(${(1 - ease(f, 35 + i * 7, 72 + i * 7)) * (i - 1) * 100}px)`,
              }}
            />
          ))}
        </g>
        <path
          d="M 960 427 V 460"
          stroke={C.copper}
          strokeWidth="1"
          opacity=".3"
        />
      </svg>
      <TrackingText
        text="agentforge."
        start={55}
        size={164}
        width={1700}
        align="center"
        style={{ position: "absolute", left: 110, top: 460 }}
      />
      <div
        style={{
          position: "absolute",
          left: 110,
          right: 110,
          top: 674,
          textAlign: "center",
        }}
      >
        <MaskReveal
          text="EVERY RUN, ACCOUNTED FOR."
          start={87}
          size={43}
          style={{ display: "flex", justifyContent: "center" }}
          color={C.muted}
        />
      </div>
      <div
        style={{
          position: "absolute",
          left: 110,
          right: 110,
          top: 809,
          textAlign: "center",
          opacity: ease(f, 114, 131),
        }}
      >
        <div style={{ fontFamily: F.sans, fontSize: 28, color: C.copper }}>
          Explore the project
        </div>
      </div>
    </AbsoluteFill>
  );
};
