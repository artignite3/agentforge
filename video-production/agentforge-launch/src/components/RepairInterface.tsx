import React from "react";
import { useCurrentFrame } from "remotion";
import { C, F } from "../styles/designTokens";
import { ease, move } from "../utils/motion";
import evidence from "../../public/reference/fixture-evidence.json";

const CodeLine: React.FC<{
  children: React.ReactNode;
  index: number;
  start: number;
  color?: string;
  size?: number;
}> = ({ children, index, start, color = C.ink, size = 27 }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ overflow: "hidden", height: size * 1.7 }}>
      <div
        style={{
          fontFamily: F.mono,
          fontSize: size,
          lineHeight: 1.7,
          color,
          whiteSpace: "pre",
          transform: `translateY(${(1 - ease(f, start + index * 3, start + index * 3 + 14)) * 50}px)`,
        }}
      >
        {children}
      </div>
    </div>
  );
};

export const RepairInterface: React.FC = () => {
  const f = useCurrentFrame();
  const state =
    f < 50
      ? "submit"
      : f < 104
        ? "fail"
        : f < 156
          ? "patch"
          : f < 220
            ? "pass"
            : "checkpoint";
  const p = ease(f, 7, 38);
  const exit = move(f, 301, 330);
  const viewStart =
    state === "submit"
      ? 16
      : state === "fail"
        ? 50
        : state === "patch"
          ? 104
          : state === "pass"
            ? 156
            : 220;
  const original = (
    state === "fail" ? evidence.before.stderr : evidence.after.stderr
  )
    .split("\n")
    .filter((x) => x.startsWith("test_"));
  return (
    <div
      style={{
        position: "absolute",
        left: 665,
        top: 300,
        width: 1148,
        height: 598,
        transform: `perspective(1700px) translate(${(1 - p) * 190 - exit * 380}px,${exit * 80}px) rotateY(${(1 - p) * -13}deg) rotateX(${(1 - p) * 5}deg) scale(${0.93 + 0.07 * p - exit * 0.05})`,
        opacity: p * (1 - exit),
        transformOrigin: "right center",
        border: "1px solid #38414a",
        background: "#12161beF",
        boxShadow: "0 32px 80px #00000050",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          height: 56,
          borderBottom: "1px solid #353c44",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 27px",
          fontFamily: F.mono,
          fontSize: 19,
          color: C.muted,
        }}
      >
        <span style={{ color: C.copper }}>agentforge. / EXECUTION TRACE</span>
        <span>
          {state === "pass" || state === "checkpoint"
            ? "COMPLETED"
            : "BOUNDED REPOSITORY REPAIR"}
        </span>
      </div>
      <div style={{ display: "flex", height: 542 }}>
        <div
          style={{
            width: 226,
            flexShrink: 0,
            borderRight: "1px solid #2d353e",
            padding: "29px 20px",
            background: "#171b20",
          }}
        >
          <div
            style={{
              fontFamily: F.sans,
              fontSize: 21,
              fontWeight: 600,
              color: C.ink,
              marginBottom: 25,
            }}
          >
            Repository repair
          </div>
          {[
            "Model decision",
            "Read file",
            "Run tests",
            "Write file",
            "Run tests",
            "Checkpoint",
          ].map((label, i) => {
            const current =
              state === "submit"
                ? 0
                : state === "fail"
                  ? 2
                  : state === "patch"
                    ? 3
                    : state === "pass"
                      ? 4
                      : 5;
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 12,
                  alignItems: "center",
                  height: 57,
                  fontFamily: F.sans,
                  fontSize: 18,
                  color: i === current ? C.ink : "#86919e",
                  borderLeft: `2px solid ${i === current ? C.copper : "#35414d"}`,
                  paddingLeft: 17,
                  background: i === current ? "#ebbc9d0c" : "transparent",
                }}
              >
                <span
                  style={{
                    width: 5,
                    height: 5,
                    background:
                      i < current
                        ? C.green
                        : i === current
                          ? C.copper
                          : "#526070",
                  }}
                />
                {label}
              </div>
            );
          })}
          <div
            style={{
              fontFamily: F.mono,
              fontSize: 13,
              color: C.muted,
              lineHeight: 1.65,
              marginTop: 22,
            }}
          >
            SCRIPTED DEMO
            <br />
            REAL DOCKER TOOLS
          </div>
        </div>
        <div
          style={{
            flex: 1,
            padding: "28px 30px",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              fontFamily: F.mono,
              fontSize: 17,
              color: C.copper,
              letterSpacing: ".1em",
              marginBottom: 22,
            }}
          >
            {state === "submit"
              ? "PYTHON SDK / SUBMIT"
              : state === "fail"
                ? "RUN TESTS / STDERR / EXIT 1"
                : state === "patch"
                  ? "WRITE FILE / STATS.PY"
                  : state === "pass"
                    ? "RUN TESTS / STDERR / EXIT 0"
                    : "CHECKPOINT / SAVED SOURCE"}
          </div>
          {state === "submit" ? (
            <div>
              <CodeLine index={0} start={16} color={C.muted} size={24}>
                from agentforge import AgentForge, Agent
              </CodeLine>
              <CodeLine index={1} start={16} size={24}>
                agent = Agent(provider="demo")
              </CodeLine>
              <CodeLine index={2} start={16} color={C.copper} size={24}>
                run = client.run(
              </CodeLine>
              <CodeLine index={3} start={16} size={24}>
                {" "}
                agent=agent, fixture="clamp",
              </CodeLine>
              <CodeLine index={4} start={16} size={24}>
                {" "}
                task="Repair and verify the tests.",
              </CodeLine>
              <CodeLine index={5} start={16} size={24}>
                {" "}
                idempotency_key="repair-001"
              </CodeLine>
              <CodeLine index={6} start={16} color={C.copper} size={24}>
                )
              </CodeLine>
            </div>
          ) : state === "patch" ? (
            <div>
              <CodeLine index={0} start={104} color={C.muted}>
                def clamp(value, low, high):
              </CodeLine>
              <div style={{ marginTop: 22, overflow: "hidden" }}>
                <div
                  style={{
                    fontFamily: F.mono,
                    fontSize: 26,
                    lineHeight: 1.8,
                    color: C.red,
                    transform: `translateX(${-ease(f, 108, 136) * 70}px)`,
                    opacity: 1 - ease(f, 126, 154),
                    whiteSpace: "pre",
                  }}
                >
                  - min(low, max(high, value))
                </div>
              </div>
              <div style={{ overflow: "hidden" }}>
                <div
                  style={{
                    fontFamily: F.mono,
                    fontSize: 26,
                    lineHeight: 1.8,
                    color: C.green,
                    transform: `translateX(${(1 - ease(f, 112, 137)) * 130}px)`,
                    whiteSpace: "pre",
                  }}
                >
                  + max(low, min(high, value))
                </div>
              </div>
              <div
                style={{
                  position: "absolute",
                  bottom: 47,
                  fontFamily: F.sans,
                  fontSize: 22,
                  color: C.muted,
                }}
              >
                Original regression tests unchanged.
              </div>
            </div>
          ) : state === "checkpoint" ? (
            <div>
              <CodeLine index={0} start={220} color={C.copper}>
                stats.py / committed source
              </CodeLine>
              <CodeLine index={1} start={220} color={C.muted} size={25}>
                def clamp(value, low, high):
              </CodeLine>
              <CodeLine index={2} start={220} color={C.green} size={25}>
                {" "}
                return max(low, min(high, value))
              </CodeLine>
              <div
                style={{
                  marginTop: 33,
                  fontFamily: F.sans,
                  fontSize: 25,
                  color: C.ink,
                  opacity: ease(f, 236, 251),
                }}
              >
                Tests passed on this saved source.
              </div>
              <div
                style={{
                  marginTop: 17,
                  fontFamily: F.mono,
                  fontSize: 18,
                  color: C.muted,
                  opacity: ease(f, 246, 261),
                }}
              >
                model decisions → tool output → checkpoint
              </div>
            </div>
          ) : (
            <div>
              {original.map((line, i) => (
                <CodeLine
                  key={i}
                  index={i}
                  start={viewStart}
                  size={23}
                  color={line.endsWith("FAIL") ? C.red : C.green}
                >
                  {line.replace("(test_stats.ClampTests.", "(")}
                </CodeLine>
              ))}
              <div
                style={{
                  marginTop: 30,
                  fontFamily: F.mono,
                  fontSize: 26,
                  color: state === "fail" ? C.red : C.green,
                  opacity: ease(f, viewStart + 15, viewStart + 29),
                }}
              >
                {state === "fail"
                  ? "FAILED (failures=2)"
                  : "OK / ORIGINAL TESTS PASSED"}
              </div>
              <div
                style={{
                  marginTop: 17,
                  fontFamily: F.sans,
                  fontSize: 24,
                  color: C.muted,
                  opacity: ease(f, viewStart + 24, viewStart + 39),
                }}
              >
                {state === "fail"
                  ? "Recorded observation. The planner can repair."
                  : "Disposable container. Saved result."}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
