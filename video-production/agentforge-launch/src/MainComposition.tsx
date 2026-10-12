import React, { useEffect, useState } from "react";
import {
  AbsoluteFill,
  Sequence,
  continueRender,
  delayRender,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { C } from "./styles/designTokens";
import { TechnicalGrid } from "./components/TechnicalGrid";
import { CheckpointWorld } from "./components/CheckpointWorld";
import { ShapeTransition } from "./components/ShapeTransition";
import { SoundDesign } from "./components/SoundDesign";
import { Scene1 } from "./scenes/Scene1";
import { Scene2 } from "./scenes/Scene2";
import { Scene3 } from "./scenes/Scene3";
import { Scene4 } from "./scenes/Scene4";
import { Scene5 } from "./scenes/Scene5";
import { ease } from "./utils/motion";

let fontPromise: Promise<void> | null = null;
function fonts() {
  if (!fontPromise)
    fontPromise = Promise.all(
      [
        ["Space Grotesk", "SpaceGrotesk.ttf", "300 700"],
        ["Inter", "Inter.ttf", "100 900"],
        ["IBM Plex Mono", "IBMPlexMono.ttf", "400"],
      ].map(async ([family, file, weight]) => {
        const face = new FontFace(
          family,
          `url(${staticFile(`fonts/${file}`)})`,
          { weight },
        );
        await face.load();
        (document.fonts as FontFaceSet & { add: (font: FontFace) => void }).add(
          face,
        );
      }),
    ).then(() => {});
  return fontPromise;
}
export const MainComposition: React.FC = () => {
  const f = useCurrentFrame();
  const [handle] = useState(() =>
    delayRender("Load locally bundled typefaces"),
  );
  const [ready, setReady] = useState(false);
  useEffect(() => {
    fonts()
      .then(() => {
        setReady(true);
        continueRender(handle);
      })
      .catch((e) => {
        throw e;
      });
  }, [handle]);
  if (!ready) return <AbsoluteFill style={{ background: C.bg }} />;
  return (
    <AbsoluteFill
      style={{ background: C.bg, color: C.ink, overflow: "hidden" }}
    >
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at 75% 49%,#1b2b3c80,transparent 58%),radial-gradient(ellipse at 20% 20%,#40302b28,transparent 45%)",
        }}
      />
      <TechnicalGrid />
      <Sequence
        from={0}
        durationInFrames={210}
        name="01 · Type behind geometry"
      >
        <Scene1 foreground={false} />
      </Sequence>
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: f >= 1110 ? 1 - ease(f, 1170, 1215) : 1,
        }}
      >
        <CheckpointWorld />
      </div>
      <Sequence from={0} durationInFrames={210} name="01 · The interruption">
        <Scene1 />
      </Sequence>
      <Sequence from={210} durationInFrames={240} name="02 · The durable core">
        <Scene2 />
      </Sequence>
      <Sequence
        from={450}
        durationInFrames={330}
        name="03 · The execution contract"
      >
        <Scene3 />
      </Sequence>
      <Sequence
        from={780}
        durationInFrames={330}
        name="04 · The inspectable repair"
      >
        <Scene4 />
      </Sequence>
      <Sequence
        from={1110}
        durationInFrames={240}
        name="05 · Every run, accounted for"
      >
        <Scene5 />
      </Sequence>
      <ShapeTransition />
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background:
            "linear-gradient(0deg,#05081150,transparent 17%,transparent 84%,#05081130)",
          boxShadow: "inset 0 0 180px #02040850",
        }}
      />
      <SoundDesign />
    </AbsoluteFill>
  );
};
