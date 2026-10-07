import { useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  Clock3,
  Code2,
  Cpu,
  Database,
  GitBranch,
  Play,
  Radio,
  Search,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { API, type Agent, type Run } from "../api";
import { terminal, duration, money, time } from "../format";
import { Badge, Empty, Stat } from "./ui";
interface Props {
  page: string;
  api: API | null;
  runs: Run[];
  agents: Agent[];
  lastSync: number | null;
  openRun: (id: string) => void;
  setCreateOpen: (open: boolean) => void;
  setConnectOpen: (open: boolean) => void;
}
export function RunsView({
  page,
  api,
  runs,
  agents,
  lastSync,
  openRun,
  setCreateOpen,
}: Props) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All statuses");
  const active = runs.filter((r) => !terminal.has(r.status)).length;
  const completed = runs.filter((r) => r.status === "COMPLETED").length;
  const finished = runs.filter((r) => terminal.has(r.status));
  const success = finished.length
    ? Math.round((completed / finished.length) * 100)
    : 0;
  const totalCost = runs.reduce((sum, r) => sum + r.spent_microusd, 0);
  const latencies = runs
    .filter((r) => terminal.has(r.status))
    .map((r) => (r.updated_at - r.created_at) * 1000)
    .sort((a, b) => a - b);
  const p50 = latencies.length
    ? latencies[Math.floor(latencies.length / 2)]
    : null;
  const visibleRuns = runs.filter(
    (r) =>
      (filter === "All statuses" || r.status === filter) &&
      `${r.id} ${r.task}`.toLowerCase().includes(search.toLowerCase()),
  );
  const agentById = Object.fromEntries(agents.map((a) => [a.id, a]));
  return (
    <>
      <div className="stats-grid">
        <Stat
          label="TOTAL RUNS"
          value={api ? String(runs.length) : "—"}
          note="Most recent 100 executions"
          icon={<Workflow size={18} />}
        />
        <Stat
          label="SUCCESS RATE"
          value={api && finished.length ? `${success}%` : "—"}
          note={`${completed} completed · ${finished.length} terminal`}
          icon={<CheckCircle2 size={18} />}
        />
        <Stat
          label="MEDIAN LATENCY"
          value={p50 === null ? "—" : duration(p50)}
          note="End-to-end · terminal runs"
          icon={<Clock3 size={18} />}
        />
        <Stat
          label="ESTIMATED SPEND"
          value={api ? money(totalCost) : "—"}
          note="Includes ambiguous reservations"
          icon={<Cpu size={18} />}
        />
      </div>
      {page === "Overview" && (
        <div className="overview-strip">
          <div className="strip-icon">
            <Radio size={19} />
          </div>
          <div>
            <strong>
              {active
                ? `${active} run${active > 1 ? "s" : ""} in flight`
                : api
                  ? "Ready for your next execution"
                  : "Your runtime, in one place"}
            </strong>
            <span>
              {api
                ? "Every completed step is saved before the next one starts."
                : "Connect to your control plane to see live runs and execution traces."}
            </span>
          </div>
          <span className="strip-tag">
            <Database size={13} />
            Durable by design
          </span>
        </div>
      )}
      <section className="panel runs-panel">
        <div className="panel-heading">
          <div className="section-title">
            <h2>{page === "Overview" ? "Recent runs" : "All runs"}</h2>
            <span className="count">{runs.length}</span>
          </div>
          <div className="live-label">
            <span className={api ? "online" : ""} />
            {api ? "Live · 4s refresh" : "Awaiting connection"}
          </div>
        </div>
        <div className="table-toolbar">
          <div className="search-input">
            <Search size={15} />
            <input
              aria-label="Search runs"
              placeholder="Search by run ID or task…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <kbd>/</kbd>
          </div>
          <select
            aria-label="Filter by status"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            {[
              "All statuses",
              "QUEUED",
              "RUNNING",
              "RETRYING",
              "COMPLETED",
              "FAILED",
              "CANCELLED",
              "TIMED_OUT",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        {visibleRuns.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>RUN / TASK</th>
                  <th>AGENT</th>
                  <th>STATUS</th>
                  <th>STEPS</th>
                  <th>LATENCY</th>
                  <th>COST</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visibleRuns.map((run) => (
                  <tr
                    key={run.id}
                    onClick={() => openRun(run.id)}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && openRun(run.id)}
                  >
                    <td>
                      <div className="run-cell">
                        <span className="run-icon">
                          <GitBranch size={15} />
                        </span>
                        <div>
                          <strong>{run.task}</strong>
                          <code>
                            {run.id.slice(0, 8)} <span>·</span>{" "}
                            {time(run.created_at)}
                          </code>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="agent-name">
                        {agentById[run.agent_id]?.name || "agent"}
                      </span>
                      <small className="table-sub">
                        {agentById[run.agent_id]?.version || "—"}
                      </small>
                    </td>
                    <td>
                      <Badge status={run.status} />
                    </td>
                    <td className="mono">{run.checkpoint_seq}</td>
                    <td className="mono">
                      {duration((run.updated_at - run.created_at) * 1000)}
                    </td>
                    <td className="mono">{money(run.spent_microusd)}</td>
                    <td>
                      <ArrowUpRight size={15} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title={
              !api
                ? "Connect your execution workspace"
                : search || filter !== "All statuses"
                  ? "No matching runs"
                  : "Your first run starts here"
            }
          >
            {!api ? (
              "Your runs, traces, and checkpoints will appear here. Your API key stays in memory for this session."
            ) : search || filter !== "All statuses" ? (
              "Try a different search or status filter."
            ) : (
              <>
                <span>
                  Launch the Repository Engineer to inspect, repair, and verify
                  a broken sample.
                </span>
                <button
                  className="button secondary"
                  onClick={() => setCreateOpen(true)}
                >
                  <Play size={14} />
                  Launch a run
                </button>
              </>
            )}
          </Empty>
        )}
        <div className="table-footer">
          <span>{visibleRuns.length} executions shown</span>
          <span>
            {lastSync
              ? `Last synced ${new Date(lastSync).toLocaleTimeString()}`
              : "No execution data loaded"}
            <ShieldCheck size={12} />
          </span>
        </div>
      </section>
      {page === "Overview" && (
        <div className="bottom-grid">
          <section className="feature-panel">
            <div className="feature-label">
              <Code2 size={15} />
              DEVELOPER FIRST
            </div>
            <h3>One API. A durable execution.</h3>
            <p>
              Submit a task once. Follow its state through failures, retries,
              and recovery.
            </p>
            <pre>
              <span>client</span>.run(agent=agent,{"\n"} task=
              <em>"Repair the failing tests"</em>)
            </pre>
            <a href="/api/docs" target="_blank" rel="noreferrer">
              Open API reference <ArrowRight size={14} />
            </a>
          </section>
          <section className="feature-panel guarantee-panel">
            <div className="feature-label">
              <ShieldCheck size={15} />
              EXECUTION GUARANTEES
            </div>
            <div className="guarantee">
              <Check size={15} />
              <span>Atomic step + checkpoint commits</span>
            </div>
            <div className="guarantee">
              <Check size={15} />
              <span>Stale workers cannot commit results</span>
            </div>
            <div className="guarantee">
              <Check size={15} />
              <span>Bounded retries and spend admission</span>
            </div>
            <div className="guarantee">
              <Check size={15} />
              <span>Isolated, resource-limited tool execution</span>
            </div>
            <div className="semantics">
              At-least-once execution · Fenced commits
            </div>
          </section>
        </div>
      )}
    </>
  );
}
