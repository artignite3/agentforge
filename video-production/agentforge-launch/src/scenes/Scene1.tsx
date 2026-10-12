import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C, F } from "../styles/designTokens";
import { ease, gate, key } from "../utils/motion";
import { FragmentText, Micro, TrackingText } from "../components/KineticText";
import { coreOutline } from "../utils/coreOutline";
export const Scene1: React.FC<{ foreground?: boolean }> = ({
  foreground = true,
}) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      {!foreground && (
        <>
          <div
            style={{
              position: "absolute",
              left: 108,
              top: 170,
              opacity: 1 - ease(f, 85, 110),
            }}
          >
            <Micro color={C.copper}>01 / THE FAILURE PATH</Micro>
            <TrackingText
              text="RUNNING"
              start={0}
              end={108}
              size={220}
              style={{ marginTop: 24 }}
            />
          </div>
          <svg
            width="1920"
            height="1080"
            style={{
              position: "absolute",
              opacity: 1 - ease(f, 85, 110),
              pointerEvents: "none",
            }}
          >
            <defs>
              <mask
                id="opening-rule-clearance"
                maskUnits="userSpaceOnUse"
                x="0"
                y="0"
                width="1920"
                height="1080"
              >
                <rect width="1920" height="1080" fill="white" />
                <polygon points={coreOutline(f)} fill="black" />
              </mask>
            </defs>
            <path
              d="M 108 484.4 H 948"
              stroke={C.copper}
              strokeWidth="2"
              fill="none"
              strokeDasharray="840"
              strokeDashoffset={840 * (1 - ease(f, 10, 38))}
              mask="url(#opening-rule-clearance)"
            />
          </svg>
        </>
      )}
      {foreground && (
        <>
          <div
            style={{
              position: "absolute",
              left: 110,
              top: 222,
              opacity: gate(f, 95, 205, 8, 12),
            }}
          >
            <FragmentText
              text={"WHAT\nSURVIVES?"}
              start={95}
              end={210}
              size={150}
              style={{ width: 1050 }}
            />
          </div>
          <div
            style={{
              position: "absolute",
              left: 114,
              bottom: 242,
              width: 750,
              opacity: ease(f, 8, 25) * (1 - ease(f, 185, 209)),
            }}
          >
            <Micro color={f >= 78 ? C.red : C.cyan}>
              {f < 78
                ? "EXECUTING / MODEL → TOOL → COMMIT"
                : "WORKER LOST / COMMITTED STATE REMAINS"}
            </Micro>
            <div
              style={{
                fontFamily: F.sans,
                fontSize: 30,
                color: C.muted,
                marginTop: 18,
                lineHeight: 1.4,
              }}
            >
              {f < 78
                ? "The loop is only the beginning."
                : "The failure path is the real system."}
            </div>
          </div>
          <svg
            width="1920"
            height="1080"
            style={{ position: "absolute", pointerEvents: "none" }}
          >
            <defs>
              <mask
                id="opening-path-clearance"
                maskUnits="userSpaceOnUse"
                x="0"
                y="0"
                width="1920"
                height="1080"
              >
                <rect width="1920" height="1080" fill="white" />
                <polygon points={coreOutline(f)} fill="black" />
              </mask>
            </defs>
            <g mask="url(#opening-path-clearance)">
              <path
                d="M 110 735 H 670 L 815 625 H 1580"
                stroke={C.copper}
                fill="none"
                strokeWidth="2"
                strokeDasharray="1600"
                strokeDashoffset={1600 * (1 - ease(f, 8, 76))}
              />
              <circle
                cx={key(f, [8, 76, 78, 108], [110, 815, 815, 815])}
                cy={key(f, [8, 76], [735, 625])}
                r={f < 78 ? 7 : 3}
                fill={f < 78 ? C.cyan : C.red}
              />
            </g>
            {[0, 1, 2, 3].map((i) => (
              <g key={i} opacity={ease(f, 110 + i * 5, 135 + i * 5)}>
                <path
                  d={`M ${120 + i * 115} 884 h 82 v 40 h -82 z`}
                  stroke={C.copper}
                  fill="#0B0F1780"
                />
                <text
                  x={130 + i * 115}
                  y="911"
                  fontFamily={F.mono}
                  fontSize="20"
                  fill={C.copper}
                >
                  CP / {i + 1}
                </text>
              </g>
            ))}
          </svg>
        </>
      )}
    </AbsoluteFill>
  );
};
