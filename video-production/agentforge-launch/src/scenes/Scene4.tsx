import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { C, F } from "../styles/designTokens";
import { ease, move } from "../utils/motion";
import {
  MaskReveal,
  Micro,
  Rule,
  StaggeredWords,
} from "../components/KineticText";
import { RepairInterface } from "../components/RepairInterface";
export const Scene4: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 110, top: 140 }}>
        <Micro color={C.copper}>04 / THE INSPECTABLE REPAIR</Micro>
        {f < 181 ? (
          <MaskReveal
            text="INSPECT THE WORK"
            start={4}
            end={185}
            size={96}
            style={{ marginTop: 18 }}
          />
        ) : (
          <StaggeredWords
            text="FOLLOW THE TRACE"
            start={178}
            end={326}
            size={95}
            style={{ marginTop: 18 }}
          />
        )}
        <Rule start={12} width={1690} />
      </div>
      <div
        style={{
          position: "absolute",
          left: 111,
          top: 347,
          width: 450,
          opacity: ease(f, 18, 40) * (1 - ease(f, 297, 327)),
        }}
      >
        <MaskReveal
          text={f < 156 ? "Repair." : "Verify."}
          start={f < 156 ? 18 : 156}
          size={64}
          color={f < 156 ? C.ink : C.green}
        />
        <div
          style={{
            fontFamily: F.sans,
            fontSize: 27,
            color: C.muted,
            lineHeight: 1.5,
            marginTop: 17,
          }}
        >
          Model decisions.
          <br />
          Tool output.
          <br />
          Saved checkpoints.
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 112,
          top: 586,
          width: 438,
          height: 258,
          overflow: "hidden",
          border: "1px solid #37414b",
          opacity: ease(f, 38, 65) * (1 - ease(f, 294, 325)),
          transform: `perspective(1300px) rotateY(${move(f, 50, 280, -7, -2)}deg)`,
        }}
      >
        <Img
          src={staticFile("reference/run-details.jpg")}
          style={{
            position: "absolute",
            width: 575,
            left: -108,
            top: -77 - move(f, 60, 280, 0, 205),
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "linear-gradient(0deg,#0B0F17c0,transparent 42%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: 16,
            left: 20,
            fontFamily: F.mono,
            fontSize: 13,
            color: C.copper,
            letterSpacing: ".08em",
          }}
        >
          GENUINE DASHBOARD CAPTURE
        </div>
      </div>
      <RepairInterface />
      <div
        style={{
          position: "absolute",
          left: 114,
          bottom: 134,
          opacity: ease(f, 20, 43) * (1 - ease(f, 307, 330)),
        }}
      >
        <Micro color={C.copper}>
          SCRIPTED DEMO / REAL ISOLATED TOOLS / ORIGINAL TESTS
        </Micro>
      </div>
    </AbsoluteFill>
  );
};
