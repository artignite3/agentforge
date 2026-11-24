import { useState } from "react";
import { ArrowUpRight, GitBranch, Play, Radio, Search } from "lucide-react";
import { API, type Agent, type Run } from "../api";
import {
  terminal,
  duration,
  money,
  runDuration,
  statusLabel,
  time,
} from "../format";
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
  // Only runs that executed at least one step; a run cancelled in the queue has no duration.
  const latencies = runs
    .filter((r) => terminal.has(r.status))
    .map(runDuration)
    .filter((ms): ms is number => ms !== null)
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
          label="Runs"
          value={api ? String(runs.length) : "—"}
          note="Latest 100"
        />
        <Stat
          label="Success rate"
          value={api && finished.length ? `${success}%` : "—"}
          note={`${completed} of ${finished.length} finished runs`}
        />
        <Stat
          label="Median duration"
          value={p50 === null ? "—" : duration(p50)}
          note="Submission to finish, runs that executed"
        />
        <Stat
          label="Estimated spend"
          value={api ? money(totalCost) : "—"}
          note="Configured rates, not an invoice"
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
                ? `${active} active run${active > 1 ? "s" : ""}`
                : api
                  ? "No active runs"
                  : "Not connected"}
            </strong>
            <span>
              {api
                ? active
                  ? "Queued, running, or waiting to retry"
                  : "New runs start as soon as a worker claims them"
                : "Connect with an API key to see runs and traces"}
            </span>
          </div>
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
              placeholder="Search runs"
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
              <option key={s} value={s}>
                {s === "All statuses" ? s : statusLabel(s)}
              </option>
            ))}
          </select>
        </div>
        {visibleRuns.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Agent</th>
                  <th>Status</th>
                  <th className="numeric">Steps</th>
                  <th className="numeric">Duration</th>
                  <th className="numeric">Cost</th>
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
                    <td className="mono numeric">{run.checkpoint_seq}</td>
                    <td className="mono numeric">
                      {(() => {
                        const ms = runDuration(run);
                        return ms === null ? "—" : duration(ms);
                      })()}
                    </td>
                    <td className="mono numeric">
                      {money(run.spent_microusd)}
                    </td>
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
                ? "Not connected"
                : search || filter !== "All statuses"
                  ? "No matching runs"
                  : "No runs yet"
            }
          >
            {!api ? (
              "Connect with an API key to see runs. The key stays in memory for this tab only."
            ) : search || filter !== "All statuses" ? (
              "Try a different search or status filter."
            ) : (
              <>
                <span>
                  Start a run to repair a bundled fixture and verify it against
                  its original tests.
                </span>
                <button
                  className="button secondary"
                  onClick={() => setCreateOpen(true)}
                >
                  <Play size={14} />
                  New run
                </button>
              </>
            )}
          </Empty>
        )}
        <div className="table-footer">
          <span>
            {visibleRuns.length} of {runs.length} runs
          </span>
          <span>
            {lastSync
              ? `Updated ${new Date(lastSync).toLocaleTimeString()}`
              : "Not loaded"}
          </span>
        </div>
      </section>
    </>
  );
}
