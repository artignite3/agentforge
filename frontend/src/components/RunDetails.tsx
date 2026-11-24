import {
  Box,
  Check,
  Clock3,
  Cpu,
  Database,
  FileCode2,
  CircleDollarSign,
  LoaderCircle,
  LockKeyhole,
  RotateCcw,
  ShieldCheck,
  Terminal,
  X,
  XCircle,
} from "lucide-react";
import { API, type Agent, type Step, type Trace, type Event } from "../api";
import {
  terminal,
  duration,
  money,
  runDuration,
  statusLabel,
  time,
} from "../format";
import { Badge, Empty, Summary } from "./ui";
import { StepRow } from "./StepRow";
/** What each write changed, reconstructed from the trace: the last content the run saw
 * for that path (a read, or an earlier write) before the write, and the written content. */
function fileChanges(steps: Step[]) {
  const known: Record<string, string> = {};
  let proposed: { path: string; content: string } | null = null;
  const changes: Record<
    string,
    { path: string; before: string; after: string }
  > = {};
  for (const step of steps) {
    if (step.status !== "SUCCEEDED") continue;
    const action = step.detail.action;
    if (step.kind === "model" && action?.operation === "write_file") {
      proposed = { path: action.path, content: action.content };
      continue;
    }
    const path = step.detail.path || "";
    if (step.detail.operation === "read_file" && step.detail.exit_code === 0)
      known[path] = step.detail.stdout || "";
    if (
      step.detail.operation === "write_file" &&
      step.detail.exit_code === 0 &&
      proposed
    ) {
      if (path in known)
        changes[step.id] = {
          path,
          before: known[path],
          after: proposed.content,
        };
      known[path] = proposed.content;
      proposed = null;
    }
  }
  return changes;
}

const EMPTY: Record<string, [string, string]> = {
  QUEUED: [
    "Waiting for a worker",
    "The run is queued in the database and starts when a worker claims it.",
  ],
  RETRYING: [
    "Waiting to retry",
    "The run is scheduled to resume after its backoff.",
  ],
  CANCELLED: [
    "Cancelled before any step ran",
    "No model or tool call was made.",
  ],
  TIMED_OUT: [
    "Timed out before any step ran",
    "The deadline passed while the run waited in the queue.",
  ],
  FAILED: ["Failed before any step ran", "See the error above for the reason."],
};

interface Props {
  selected: string;
  trace: Trace | null;
  agentById: Record<string, Agent>;
  busy: boolean;
  operate: (action: () => Promise<unknown>) => Promise<void>;
  api: API | null;
  openRun: (id: string) => void;
  setSelected: (id: string | null) => void;
  setTrace: (trace: Trace | null) => void;
  tab: string;
  setTab: (tab: string) => void;
  expanded: string | null;
  setExpanded: (id: string | null) => void;
  events: Event[];
}
export function RunDetails({
  selected,
  trace,
  agentById,
  busy,
  operate,
  api,
  openRun,
  setSelected,
  setTrace,
  tab,
  setTab,
  expanded,
  setExpanded,
  events,
}: Props) {
  return (
    <>
      <button
        className="back-link"
        onClick={() => {
          setSelected(null);
          setTrace(null);
        }}
      >
        ← All runs
      </button>
      <div className="page-heading">
        <div>
          <h1>
            Repository repair{" "}
            <span className="heading-id">/{selected.slice(0, 8)}</span>
          </h1>
          <p>{trace?.run.task || "Loading execution state…"}</p>
        </div>
        <div className="heading-actions">
          {trace && <Badge status={trace.run.status} />}
          {trace && !terminal.has(trace.run.status) && (
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => void operate(() => api!.cancel(selected))}
            >
              <X size={15} />
              Cancel run
            </button>
          )}
          {trace &&
            terminal.has(trace.run.status) &&
            trace.run.status !== "COMPLETED" && (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() =>
                  void operate(async () => {
                    const r = await api!.retry(selected);
                    openRun(r.id);
                  })
                }
              >
                <RotateCcw size={15} />
                Retry as new run
              </button>
            )}
        </div>
      </div>
      {trace ? (
        <>
          <div className="run-summary">
            <Summary
              label="Agent version"
              value={`${agentById[trace.run.agent_id]?.name || "agent"} / ${agentById[trace.run.agent_id]?.version || "—"}`}
              icon={<Box size={16} />}
            />
            <Summary
              label="Elapsed"
              value={(() => {
                const ms = runDuration(trace.run);
                return ms === null ? "—" : duration(ms);
              })()}
              icon={<Clock3 size={16} />}
            />
            <Summary
              label="Charged usage"
              value={`${trace.run.charged_tokens.toLocaleString()} tokens`}
              icon={<Cpu size={16} />}
            />
            <Summary
              label="Estimated spend"
              value={money(trace.run.spent_microusd)}
              icon={<CircleDollarSign size={16} />}
            />
          </div>
          {trace.run.error_type && (
            <div className="error-banner">
              <XCircle size={16} />
              {trace.run.error_type}
            </div>
          )}
          <div className="trace-layout">
            <section className="panel trace-panel">
              <div className="tabs">
                {["Timeline", "Events", "Checkpoint"].map((t) => (
                  <button
                    key={t}
                    className={tab === t ? "active" : ""}
                    onClick={() => setTab(t)}
                  >
                    {t}
                    {t === "Timeline" && <span>{trace.steps.length}</span>}
                  </button>
                ))}
              </div>
              {tab === "Timeline" && (
                <div className="timeline">
                  {(() => {
                    const changes = fileChanges(trace.steps);
                    return trace.steps.map((step) => (
                      <StepRow
                        key={step.id}
                        step={step}
                        change={changes[step.id]}
                        expanded={expanded === step.id}
                        onClick={() =>
                          setExpanded(expanded === step.id ? null : step.id)
                        }
                      />
                    ));
                  })()}
                  {!trace.steps.length && (
                    <Empty title={(EMPTY[trace.run.status] ?? EMPTY.QUEUED)[0]}>
                      {(EMPTY[trace.run.status] ?? EMPTY.QUEUED)[1]}
                    </Empty>
                  )}
                  <div className="timeline-end">
                    <span
                      className={`timeline-node ${trace.run.status === "COMPLETED" ? "done" : ""}`}
                    >
                      <Check size={13} />
                    </span>
                    <strong>
                      {terminal.has(trace.run.status)
                        ? statusLabel(trace.run.status)
                        : "In progress"}
                    </strong>
                  </div>
                </div>
              )}
              {tab === "Events" && (
                <div className="event-list">
                  {events.map((event) => (
                    <div key={event.id}>
                      <code>{time(event.at)}</code>
                      <span>{event.kind}</span>
                      <pre>{JSON.stringify(event.data, null, 2)}</pre>
                    </div>
                  ))}
                </div>
              )}
              {tab === "Checkpoint" && (
                <div className="checkpoint">
                  <div className="checkpoint-heading">
                    <Database size={17} />
                    <strong>
                      Checkpoint {trace.checkpoint?.sequence ?? 0}
                    </strong>
                    <span>schema v{trace.checkpoint?.schema_version ?? 1}</span>
                  </div>
                  <p>
                    Saved in the same transaction as the step that produced it.
                    A recovered worker resumes from here.
                  </p>
                  {Object.entries(trace.checkpoint?.payload.files || {}).map(
                    ([name, source]) => (
                      <div className="source-file" key={name}>
                        <div>
                          <FileCode2 size={14} />
                          {name}
                        </div>
                        <pre>{source}</pre>
                      </div>
                    ),
                  )}
                </div>
              )}
            </section>
            <aside className="run-aside">
              <section className="panel">
                <div className="panel-heading">
                  <h3>Run details</h3>
                  <LockKeyhole size={15} />
                </div>
                <dl>
                  <dt>Run ID</dt>
                  <dd className="mono wrap">{selected}</dd>
                  <dt>Repository fixture</dt>
                  <dd>{trace.run.fixture}</dd>
                  <dt>Checkpoint</dt>
                  <dd>{trace.run.checkpoint_seq} committed steps</dd>
                  <dt>Worker recoveries</dt>
                  <dd>{trace.run.recoveries}</dd>
                  <dt>Deadline</dt>
                  <dd>{time(trace.run.deadline)}</dd>
                  <dt>Verification</dt>
                  <dd
                    className={
                      trace.checkpoint?.payload.tests_passed ? "text-green" : ""
                    }
                  >
                    {trace.checkpoint?.payload.tests_passed
                      ? "Regression tests passed"
                      : terminal.has(trace.run.status)
                        ? "Not verified"
                        : "Awaiting passing tests"}
                  </dd>
                </dl>
              </section>
              <section className="panel">
                <div className="panel-heading">
                  <h3>Model explanation (not verified)</h3>
                  <Terminal size={15} />
                </div>
                <p className="agent-output">
                  {trace.run.output ||
                    (terminal.has(trace.run.status)
                      ? "No explanation: the run ended without a finish step."
                      : "Appears when the planner finishes.")}
                </p>
                <p className="agent-output-note">
                  Written by the planner. Completion is decided by the test
                  result, not by this text.
                </p>
              </section>
              <div className="security-caption">
                <ShieldCheck size={15} />
                Tool code runs in disposable containers with network access
                disabled.
              </div>
            </aside>
          </div>
        </>
      ) : (
        <div className="loading">
          <LoaderCircle className="spin" size={24} />
          Loading trace…
        </div>
      )}
    </>
  );
}
