import { Easing, interpolate } from "remotion";
export const clamp = (n: number, a = 0, b = 1) => Math.max(a, Math.min(b, n));
export const out = Easing.bezier(0.16, 1, 0.3, 1);
export const smooth = Easing.bezier(0.65, 0, 0.35, 1);
export const ease = (f: number, a: number, b: number, from = 0, to = 1) =>
  interpolate(f, [a, b], [from, to], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: out,
  });
export const move = (f: number, a: number, b: number, from = 0, to = 1) =>
  interpolate(f, [a, b], [from, to], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smooth,
  });
export const gate = (
  f: number,
  start: number,
  end: number,
  attack = 14,
  release = 14,
) => ease(f, start, start + attack) * (1 - ease(f, end - release, end));
export const key = (f: number, times: number[], values: number[]) =>
  interpolate(f, times, values, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smooth,
  });
