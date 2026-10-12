import React from "react";
import { useCurrentFrame, spring } from "remotion";
import { C, F } from "../styles/designTokens";
import { ease, key } from "../utils/motion";

type TextProps = {
  text: string;
  start: number;
  end?: number;
  size?: number;
  color?: string;
  style?: React.CSSProperties;
  delay?: number;
  direction?: "up" | "left" | "right";
  weight?: number;
};
export const MaskReveal: React.FC<TextProps> = ({
  text,
  start,
  end = 1500,
  size = 110,
  color = C.ink,
  style,
  direction = "up",
  weight = 600,
}) => {
  const f = useCurrentFrame();
  const p = ease(f, start, start + 25);
  const exit = ease(f, end - 16, end);
  const x = direction === "left" ? -120 : direction === "right" ? 120 : 0;
  return (
    <div style={{ overflow: "hidden", lineHeight: 1.08, ...style }}>
      <div
        style={{
          fontFamily: F.display,
          fontSize: size,
          fontWeight: weight,
          letterSpacing: ".025em",
          color,
          whiteSpace: "pre",
          transform: `translate(${x * (1 - p) + exit * -60}px,${(direction === "up" ? size * 1.2 : 0) * (1 - p) - exit * size * 1.1}px)`,
          filter: `blur(${(1 - p) * 3 + exit * 4}px)`,
        }}
      >
        {text}
      </div>
    </div>
  );
};

export const TrackingText: React.FC<
  TextProps & { width?: number; align?: "left" | "center"; overshoot?: boolean }
> = ({
  text,
  start,
  end = 1500,
  size = 160,
  color = C.ink,
  style,
  width = 1700,
  align = "left",
  overshoot = true,
}) => {
  const f = useCurrentFrame();
  const spacing = key(
    f,
    [start, start + 18, start + 40],
    [size * -0.09, size * 0.075, size * 0.018],
  );
  const p = ease(f, start, start + 23),
    exit = ease(f, end - 18, end);
  const s = overshoot
    ? spring({
        frame: f - start,
        fps: 30,
        config: { damping: 22, stiffness: 130, mass: 0.8 },
      })
    : p;
  const ctx = document.createElement("canvas").getContext("2d")!;
  ctx.font = `600 ${size}px "${F.display}"`;
  const widths = [...text].map((c) => ctx.measureText(c).width);
  const total = widths.reduce((a, b) => a + b, 0) + spacing * (text.length - 1);
  let cursor = align === "center" ? (width - total) / 2 : 0;
  return (
    <div
      style={{
        position: "relative",
        width,
        height: size * 1.18,
        overflow: "hidden",
        ...style,
      }}
    >
      {[...text].map((c, i) => {
        const x = cursor;
        cursor += widths[i] + spacing;
        const reveal = ease(f, start + i * 0.75, start + 22 + i * 0.75);
        return (
          <span
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: 0,
              fontFamily: F.display,
              fontWeight: 600,
              fontSize: size,
              color,
              whiteSpace: "pre",
              lineHeight: 1.1,
              transform: `translateY(${(1 - reveal) * size * 1.15 - exit * size * 1.2}px) scale(${0.97 + 0.03 * s}) rotateY(${(1 - reveal) * (i % 2 ? 18 : -18)}deg)`,
              opacity: p ? 1 : 0,
            }}
          >
            {c}
          </span>
        );
      })}
    </div>
  );
};

export const StaggeredWords: React.FC<TextProps> = ({
  text,
  start,
  end = 1500,
  size = 110,
  color = C.ink,
  style,
  delay = 5,
}) => {
  const f = useCurrentFrame();
  return (
    <div
      style={{
        display: "flex",
        gap: size * 0.22,
        fontFamily: F.display,
        fontSize: size,
        fontWeight: 600,
        letterSpacing: ".015em",
        lineHeight: 1.1,
        ...style,
      }}
    >
      {text.split(" ").map((word, i) => {
        const p = ease(f, start + i * delay, start + 24 + i * delay);
        const e = ease(f, end - 16, end);
        return (
          <div key={i} style={{ overflow: "hidden" }}>
            <div
              style={{
                transform: `translate(${(1 - p) * (i % 2 ? 55 : -55)}px,${(1 - p) * size * 1.2 - e * size * 1.2}px)`,
              }}
            >
              <span style={{ color }}>{word}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export const Micro: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  color?: string;
}> = ({ children, style, color = C.muted }) => (
  <div
    style={{
      fontFamily: F.mono,
      fontSize: 22,
      letterSpacing: ".12em",
      lineHeight: 1.4,
      color,
      ...style,
    }}
  >
    {children}
  </div>
);
export const Rule: React.FC<{
  start: number;
  width?: number;
  color?: string;
  style?: React.CSSProperties;
}> = ({ start, width = 500, color = C.copper, style }) => {
  const f = useCurrentFrame();
  return (
    <div
      style={{
        height: 2,
        width,
        background: color,
        transform: `scaleX(${ease(f, start, start + 28)})`,
        transformOrigin: "left",
        ...style,
      }}
    />
  );
};
export const FragmentText: React.FC<TextProps> = ({
  text,
  start,
  end = 1500,
  size = 132,
  style,
  color = C.ink,
}) => {
  const f = useCurrentFrame();
  const p = ease(f, start, start + 28);
  const exit = ease(f, end - 22, end);
  return (
    <div
      style={{
        position: "relative",
        height: size * 2.3,
        overflow: "hidden",
        ...style,
      }}
    >
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            fontFamily: F.display,
            fontSize: size,
            fontWeight: 600,
            lineHeight: 1.05,
            letterSpacing: ".01em",
            color,
            whiteSpace: "pre",
            clipPath: `inset(${i * 33.333}% 0 ${100 - (i + 1) * 33.333}% 0)`,
            transform: `translate(${(1 - p) * (i - 1) * 240 + exit * (i - 1) * 220}px,${(1 - p) * (i - 1) * 65}px)`,
            opacity: 1 - exit,
          }}
        >
          {text}
        </div>
      ))}
    </div>
  );
};
