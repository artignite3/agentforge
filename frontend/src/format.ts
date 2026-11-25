import type { Run } from "./api";

export const terminal = new Set([
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "TIMED_OUT",
]);

/** One money format: model calls cost fractions of a cent, so sub-dollar amounts keep 4 decimals. */
export const money = (micro: number) => {
  if (!micro) return "$0";
  const usd = micro / 1e6;
  return `$${usd.toFixed(usd < 1 ? 4 : 2)}`;
};

export const duration = (ms: number) =>
  ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;

/** Wall time from submission to the last update, or null for runs that never executed a step. */
export const runDuration = (run: Run) =>
  run.checkpoint_seq === 0 && run.status !== "RUNNING"
    ? null
    : (run.updated_at - run.created_at) * 1000;

export const statusLabel = (status: string) => {
  const text = status.replaceAll("_", " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
};

export const time = (epoch: number) =>
  new Date(epoch * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
