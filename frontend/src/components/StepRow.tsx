import { X, Cpu, Terminal, ChevronDown } from "lucide-react";
import type { Step } from "../api";
import { duration, money } from "../format";
export function StepRow({
  step,
  expanded,
  onClick,
}: {
  step: Step;
  expanded: boolean;
  onClick: () => void;
}) {
  const isModel = step.kind === "model";
  const failed = step.status === "FAILED" || step.status === "UNKNOWN";
  const title = isModel
    ? "Model decision"
    : (step.detail.operation || "Tool execution").replaceAll("_", " ");
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
            <code>{isModel ? step.model : step.detail.path || "sandbox"}</code>
          </div>
          <p>
            {step.error_type ||
              (isModel
                ? step.routing_reason
                : step.detail.exit_code !== undefined
                  ? `Exit code ${step.detail.exit_code} · isolated container`
                  : "Executing operation")}
          </p>
        </div>
        <span className="step-duration">
          {step.duration_ms === null
            ? step.status === "STARTED"
              ? "in flight"
              : "unrecorded"
            : duration(step.duration_ms)}
        </span>
        <ChevronDown size={14} className={expanded ? "rotate" : ""} />
      </button>
      {expanded && (
        <div className="step-detail">
          {step.detail.action && <p>{step.detail.action.explanation}</p>}
          {step.detail.stdout && (
            <>
              <label>STDOUT</label>
              <pre>{step.detail.stdout}</pre>
            </>
          )}
          {step.detail.stderr && (
            <>
              <label>STDERR</label>
              <pre>{step.detail.stderr}</pre>
            </>
          )}
          {isModel && (
            <div className="step-usage">
              <span>{step.tokens} tokens</span>
              <span>{money(step.cost_microusd)}</span>
              <span>{step.provider}</span>
            </div>
          )}
          {step.detail.action?.content && (
            <pre>{step.detail.action.content}</pre>
          )}
        </div>
      )}
    </div>
  );
}
