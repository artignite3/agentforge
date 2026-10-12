import React from "react";
import { Composition } from "remotion";
import { MainComposition } from "./MainComposition";
export const RemotionRoot: React.FC = () => (
  <Composition
    id="AgentForgeLaunch"
    component={MainComposition}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={1350}
  />
);
