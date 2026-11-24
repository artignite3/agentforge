import { X, Cpu, Terminal, ChevronDown, FileCode2 } from "lucide-react";
import type { Step } from "../api";
import { duration, money } from "../format";

const TITLES: Record<string, string> = {
  read_file: "Read file",
  write_file: "Write file",
  run_tests: "Run tests",
};

/** unittest's own summary, e.g. "Ran 4 tests" + "FAILED (failures=1)" or "OK". */
export function testSummary(stderr = "") {
  const ran = stderr.match(/Ran (\d+) tests?/);
  const lines = stderr.trimEnd().split("\n");
  const last = lines[lines.length - 1]?.trim() ?? "";
  if (!ran) return null;
  const failures = last.match(/failures=(\d+)/)?.[1];
  const errors = last.match(/errors=(\d+)/)?.[1];
  const problems = Number(failures ?? 0) + Number(errors ?? 0);
  return {
    passed: last === "OK",
    text:
      last === "OK"
        ? `${ran[1]} tests passed`
        : `${problems || "Some"} of ${ran[1]} tests failed`,
  };
}

type DiffLine = { kind: "same" | "add" | "del"; text: string };

/** Line diff by longest common subsequence; fixture files are tiny, so O(n·m) is fine. */
export function lineDiff(before: string, after: string): DiffLine[] {
  const a = before.split("\n");
  const b = after.split("\n");
  const lcs = Array.from({ length: a.length + 1 }, () =>
    new Array<number>(b.length + 1).fill(0),
  );
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      lcs[i][j] =
        a[i] === b[j]
          ? lcs[i + 1][j + 1] + 1
          : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) (out.push({ kind: "same", text: a[i++] }), j++);
    else if (lcs[i + 1][j] >= lcs[i][j + 1])
      out.push({ kind: "del", text: a[i++] });
    else out.push({ kind: "add", text: b[j++] });
  }
  while (i < a.length) out.push({ kind: "del", text: a[i++] });
  while (j < b.length) out.push({ kind: "add", text: b[j++] });
  while (
    out.length &&
    out[out.length - 1].text === "" &&
    out[out.length - 1].kind === "same"
  )
    out.pop();
  return out;
}

export function Diff({ path, lines }: { path: string; lines: DiffLine[] }) {
  return (
    <div className="diff">
      <div className="diff-heading">
        <FileCode2 size={14} />
        {path}
        <span>
          +{lines.filter((l) => l.kind === "add").length} −
          {lines.filter((l) => l.kind === "del").length}
        </span>
      </div>
      <pre>
        {lines.map((line, index) => (
          <span key={index} className={`diff-${line.kind}`}>
            {line.kind === "add" ? "+ " : line.kind === "del" ? "− " : "  "}
            {line.text}
            {"\n"}
          </span>
        ))}
      </pre>
    </div>
  );
}

export function StepRow({
  step,
  expanded,
  onClick,
  change,
}: {
  step: Step;
  expanded: boolean;
  onClick: () => void;
  /** For a write: the file before and after, when the trace shows both. */
  change?: { path: string; before: string; after: string };
}) {
  const isModel = step.kind === "model";
  const failed = step.status === "FAILED" || step.status === "UNKNOWN";
  const operation = step.detail.operation || "";
  const title = isModel
    ? "Model decision"
    : TITLES[operation] || "Tool execution";
  const tests =
    operation === "run_tests" ? testSummary(step.detail.stderr) : null;
  const rejected = step.detail.stderr?.startsWith("Rejected by policy: ")
    ? step.detail.stderr.slice("Rejected by policy: ".length)
    : null;
  const summary =
    step.error_type ||
    (isModel
      ? step.routing_reason
      : rejected
        ? `Rejected before execution: ${rejected}`
        : tests
          ? tests.text
          : step.detail.exit_code !== undefined
            ? `Exit code ${step.detail.exit_code}`
            : "Running");
  const diff =
    change && change.before !== change.after
      ? lineDiff(change.before, change.after)
      : null;
  return (
    <div className={`timeline-step ${failed ? "step-failed" : ""}`}>
      <span
        className={`timeline-node ${failed ? "failed" : step.status === "SUCCEEDED" ? "done" : ""}`}
      >
        {failed ? (
          <X size={12} />
        ) : isModel ? (
          <Cpu size={12} />
        ) : (
          <Terminal size={12} />
        )}
      </span>
      <button className="step-header" onClick={onClick}>
        <div>
          <div className="step-title">
            <strong>{title}</strong>
            {step.attempt > 1 && (
              <span className="attempt">attempt {step.attempt}</span>
            )}
            <code>
              {isModel ? step.model : step.detail.path || "workspace"}
            </code>
          </div>
          <p
            className={
              tests
                ? tests.passed
                  ? "outcome-pass"
                  : "outcome-fail"
                : rejected
                  ? "outcome-fail"
                  : ""
            }
          >
            {summary}
          </p>
        </div>
        {step.status === "SUCCEEDED" && (
          <span
            className="checkpoint-mark"
            title="Checkpoint committed by this step"
          >
            #{step.sequence + 1}
          </span>
        )}
        <span className="step-duration">
          {step.duration_ms === null
            ? step.status === "STARTED"
              ? "in flight"
              : "—"
            : duration(step.duration_ms)}
        </span>
        <ChevronDown size={14} className={expanded ? "rotate" : ""} />
      </button>
      {diff && <Diff path={change!.path} lines={diff} />}
      {expanded && (
        <div className="step-detail">
          {step.detail.action?.explanation && (
            <p>{step.detail.action.explanation}</p>
          )}
          {step.detail.stdout && (
            <>
              <label>Output</label>
              <pre>{step.detail.stdout}</pre>
            </>
          )}
          {step.detail.stderr && (
            <>
              <label>{tests ? "Test output" : "Errors"}</label>
              <pre>{step.detail.stderr}</pre>
            </>
          )}
          {isModel && (
            <div className="step-usage">
              <span>{step.tokens.toLocaleString()} tokens</span>
              <span>{money(step.cost_microusd)}</span>
              <span>{step.provider}</span>
            </div>
          )}
          {step.detail.action?.content && (
            <>
              <label>
                Proposed{" "}
                {step.detail.action.operation === "write_file"
                  ? "file"
                  : "content"}
              </label>
              <pre>{step.detail.action.content}</pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}
