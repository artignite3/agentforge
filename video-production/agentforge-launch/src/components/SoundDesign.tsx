import React from "react";
import { Audio, staticFile } from "remotion";
export const SoundDesign: React.FC = () => (
  <Audio src={staticFile("audio/master.wav")} volume={1} />
);
