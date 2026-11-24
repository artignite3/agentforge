import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  Box,
  ChevronDown,
  ChevronRight,
  Circle,
  Clock3,
  Cpu,
  Database,
  GitBranch,
  Layers3,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  Plus,
  RefreshCw,
  Server,
  ShieldCheck,
  Unplug,
  Workflow,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import {
  API,
  type Agent,
  type Event,
  type Provider,
  type Run,
  type System,
  type Trace,
} from "./api";
import { terminal } from "./format";
import { Empty, Health } from "./components/ui";
import { RunDetails } from "./components/RunDetails";
import { RunsView } from "./components/RunsView";
import { Modal, RunModal, AgentModal } from "./components/Dialogs";
type Page = "Overview" | "Runs" | "Agents" | "Providers" | "System health";
export default function App() {
  const [page, setPage] = useState<Page>("Overview");
  const [api, setAPI] = useState<API | null>(null);
  const [key, setKey] = useState("");
  const [connectOpen, setConnectOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [agentOpen, setAgentOpen] = useState(false);
  const [runs, setRuns] = useState<Run[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [system, setSystem] = useState<System | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  // Last event id fetched for the selected run; the API pages 200 events per request.
  const eventCursor = useRef<{ run: string | null; id: number }>({
    run: null,
    id: 0,
  });
  const [tab, setTab] = useState("Timeline");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastSync, setLastSync] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    if (!api) return;
    try {
      const [r, a] = await Promise.all([api.runs(), api.agents()]);
      setRuns(r);
      setAgents(a);
      setLastSync(Date.now());
      setError("");
      if (selected) {
        const after =
          eventCursor.current.run === selected ? eventCursor.current.id : 0;
        const [t, e] = await Promise.all([
          api.trace(selected),
          api.events(selected, after),
        ]);
        setTrace(t);
        if (after === 0) setEvents(e);
        else if (e.length) setEvents((previous) => [...previous, ...e]);
        if (e.length)
          eventCursor.current = { run: selected, id: e[e.length - 1].id };
        else if (after === 0) eventCursor.current = { run: selected, id: 0 };
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection failed");
    }
  }, [api, selected]);

  useEffect(() => {
    void refresh();
    const handle = setInterval(() => void refresh(), 4000);
    return () => clearInterval(handle);
  }, [refresh]);
  useEffect(() => {
    if (!api) return;
    // Worker liveness changes over time; poll it more slowly than runs.
    const load = () =>
      Promise.all([api.providers(), api.system()])
        .then(([p, s]) => {
          setProviders(p);
          setSystem(s);
        })
        .catch((e) => setError(String(e)));
    void load();
    const handle = setInterval(() => void load(), 15000);
    return () => clearInterval(handle);
  }, [api]);

  async function connect(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const client = new API(key);
    try {
      await client.system();
      setAPI(client);
      setKey("");
      setConnectOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to connect");
    } finally {
      setBusy(false);
    }
  }
  async function operate(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  function navigate(next: Page) {
    setPage(next);
    setSelected(null);
    setTrace(null);
  }
  function openRun(id: string) {
    setSelected(id);
    setTrace(null);
    setPage("Runs");
    setTab("Timeline");
  }
  function disconnect() {
    setAPI(null);
    setRuns([]);
    setAgents([]);
    setProviders([]);
    setSystem(null);
    setTrace(null);
    setSelected(null);
    setLastSync(null);
  }

  const active = runs.filter((r) => !terminal.has(r.status)).length;
  const agentById = Object.fromEntries(agents.map((a) => [a.id, a]));

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => navigate("Overview")}>
          <span className="brand-mark">
            <Layers3 size={22} strokeWidth={2.4} />
          </span>
          agentforge<span className="brand-period">.</span>
        </button>
        <div className="workspace">
          <div className="workspace-avatar">AF</div>
          <div>
            <strong>Development</strong>
            <span>Execution workspace</span>
          </div>
          <ChevronDown size={14} />
        </div>
        <div className="nav-label">CONTROL PLANE</div>
        <nav>
          {(
            [
              ["Overview", LayoutDashboard],
              ["Runs", Workflow],
              ["Agents", Box],
              ["Providers", GitBranch],
              ["System health", Activity],
            ] as const
          ).map(([name, Icon]) => (
            <button
              key={name}
              className={`nav-item ${page === name ? "selected" : ""}`}
              onClick={() => navigate(name)}
            >
              <Icon size={18} />
              <span>{name}</span>
              {name === "Runs" && active > 0 && <small>{active}</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <div>
            <ShieldCheck size={17} />
            <span>Built for the failure path</span>
          </div>
          <p>Fenced leases. Durable checkpoints. Observable execution.</p>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            Explore the API <ArrowUpRight size={13} />
          </a>
        </div>
        <div className="sidebar-bottom">
          <span className={`connection-dot ${api ? "online" : ""}`} />
          <span>{api ? "Workspace connected" : "Workspace disconnected"}</span>
          <button
            aria-label={api ? "Disconnect" : "Connect workspace"}
            onClick={() => (api ? disconnect() : setConnectOpen(true))}
          >
            <Unplug size={15} />
          </button>
        </div>
        <div className="version">
          AGENTFORGE <span>v0.1.0</span>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{page}</strong>
            {selected && (
              <>
                <ChevronRight size={13} />
                <code>{selected.slice(0, 8)}</code>
              </>
            )}
          </div>
          <div className="topbar-right">
            <span className="environment">
              <span />
              {system?.environment || "Local environment"}
              {system &&
                ` · ${system.principal.label} (${system.principal.role})`}
            </span>
            <button
              className="icon-button"
              title="Refresh"
              onClick={() => void refresh()}
            >
              <RefreshCw size={16} />
            </button>
            <button
              className="avatar"
              onClick={() => setConnectOpen(true)}
              aria-label="Connection settings"
            >
              AF
            </button>
          </div>
        </header>
        <main>
          {error && !connectOpen && (
            <div className="error-banner" role="alert">
              <XCircle size={16} />
              {error}
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={14} />
              </button>
            </div>
          )}
          {selected ? (
            <RunDetails
              {...{
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
              }}
            />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">AGENT EXECUTION PLATFORM</div>
                  <h1>
                    {page === "Overview"
                      ? "Every run, accounted for."
                      : page === "Runs"
                        ? "Execution runs"
                        : page === "Agents"
                          ? "Your agent fleet"
                          : page === "Providers"
                            ? "Model routing"
                            : "System health"}
                  </h1>
                  <p>
                    {page === "Overview"
                      ? "Inspect the work. Understand the failures. Resume with confidence."
                      : page === "Runs"
                        ? "Durable jobs, from submission through the last checkpoint."
                        : page === "Agents"
                          ? "Immutable configurations. Explicit limits. Reproducible behavior."
                          : page === "Providers"
                            ? "Provider-neutral execution with visible, rules-based decisions."
                            : "The dependencies behind reliable agent execution."}
                  </p>
                </div>
                <button
                  className="button primary"
                  onClick={() =>
                    api ? setCreateOpen(true) : setConnectOpen(true)
                  }
                >
                  <Plus size={16} />
                  {api ? "New run" : "Connect workspace"}
                </button>
              </div>
              {(page === "Overview" || page === "Runs") && (
                <RunsView
                  key={page}
                  {...{
                    page,
                    api,
                    runs,
                    agents,
                    lastSync,
                    openRun,
                    setCreateOpen,
                    setConnectOpen,
                  }}
                />
              )}
              {page === "Agents" && (
                <section className="panel">
                  <div className="panel-heading">
                    <h2>
                      Registered agents{" "}
                      <span className="count">{agents.length}</span>
                    </h2>
                    <button
                      className="button secondary"
                      onClick={() =>
                        api ? setAgentOpen(true) : setConnectOpen(true)
                      }
                    >
                      <Plus size={14} />
                      Register agent
                    </button>
                  </div>
                  {agents.length ? (
                    <div className="agent-grid">
                      {agents.map((a) => (
                        <div className="agent-card" key={a.id}>
                          <div className="agent-card-top">
                            <span className="agent-box">
                              <Box size={22} />
                            </span>
                            <span className="version-tag">{a.version}</span>
                          </div>
                          <h3>{a.name}</h3>
                          <p>{a.config.instructions}</p>
                          <div className="agent-limits">
                            <span>
                              <Cpu size={13} />
                              {a.config.provider}
                            </span>
                            <span>
                              <Clock3 size={13} />
                              {a.config.timeout}s
                            </span>
                            <span>{a.config.max_steps} steps</span>
                          </div>
                          <div className="agent-card-footer">
                            <code>{a.id.slice(0, 8)}</code>
                            <button onClick={() => setCreateOpen(true)}>
                              Run agent <ArrowUpRight size={14} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty
                      title="Give your runtime its first agent"
                      icon={<Box size={27} />}
                    >
                      Register an immutable agent configuration or launch a run
                      to create the default Repository Engineer.
                    </Empty>
                  )}
                </section>
              )}
              {page === "Providers" && (
                <>
                  <div className="notice">
                    <GitBranch size={17} />
                    <div>
                      <strong>Simple routing. Visible decisions.</strong>
                      <p>
                        Auto routing chooses the lowest estimated cost within
                        budget, then prefers providers with fewer failed
                        attempts. Every decision is recorded in the trace.
                      </p>
                    </div>
                  </div>
                  <div className="provider-grid">
                    {providers.length ? (
                      providers.map((p) => (
                        <section
                          className="panel provider-card"
                          key={p.provider}
                        >
                          <div className="provider-symbol">
                            <Cpu size={23} />
                          </div>
                          <div className="provider-heading">
                            <h3>
                              {p.provider === "demo"
                                ? "Deterministic demo"
                                : p.provider === "openai"
                                  ? "OpenAI"
                                  : "Google Gemini"}
                            </h3>
                            <span
                              className={`config-tag ${p.configured ? "enabled" : ""}`}
                            >
                              {p.configured ? "Configured" : "Not configured"}
                            </span>
                          </div>
                          <code>{p.model}</code>
                          <p>
                            {p.provider === "demo"
                              ? "Scripted fixture planner. No model inference, token usage, or provider cost."
                              : "Live provider adapter. Availability is established by actual requests; configuration alone is not a health check."}
                          </p>
                          <div className="provider-footer">
                            <Circle size={11} />
                            {p.health === "fixture"
                              ? "Reproducible fixture"
                              : "Health not probed"}
                          </div>
                        </section>
                      ))
                    ) : (
                      <Empty
                        title="Connect to inspect providers"
                        icon={<GitBranch size={27} />}
                      >
                        Provider keys are configured on the server.
                      </Empty>
                    )}
                  </div>
                </>
              )}
              {page === "System health" && (
                <div className="health-grid">
                  <Health
                    icon={<Server />}
                    name="API / control plane"
                    value={api ? "Connected" : "Disconnected"}
                    detail="Authenticated REST API · automatic OpenAPI"
                    good={!!api}
                  />
                  <Health
                    icon={<Database />}
                    name="Durable queue"
                    value={system?.queue || "Unknown"}
                    detail="Runs, leases, events, and checkpoints share one database."
                    good={!!system}
                  />
                  <Health
                    icon={<ShieldCheck />}
                    name="Tool isolation"
                    value={
                      system
                        ? system.sandbox_ready
                          ? "Ready"
                          : "Unavailable"
                        : "Unknown"
                    }
                    detail="Gateway and tool image readiness, reported by live workers."
                    good={system?.sandbox_ready === true}
                  />
                  <Health
                    icon={<Cpu />}
                    name="Workers"
                    value={system ? `${system.workers_alive} alive` : "Unknown"}
                    detail="Workers heartbeat every 5 s; none alive means queued runs wait."
                    good={(system?.workers_alive ?? 0) > 0}
                  />
                  <Health
                    icon={<Activity />}
                    name="Execution semantics"
                    value="At least once"
                    detail="Only a worker holding the current lease can commit."
                    good={true}
                  />
                </div>
              )}
            </>
          )}
          <footer className="page-footer">
            <span>AgentForge / execution control plane</span>
            <span>
              Designed for observable, recoverable work{" "}
              <ArrowDownLeft size={12} />
            </span>
          </footer>
        </main>
      </div>

      {connectOpen && (
        <Modal
          title="Connect your workspace"
          subtitle="Use the API key from your server environment."
          onClose={() => setConnectOpen(false)}
        >
          <form onSubmit={connect}>
            <label htmlFor="api-key">API KEY</label>
            <input
              id="api-key"
              type="password"
              autoFocus
              autoComplete="off"
              spellCheck={false}
              placeholder="Paste AGENTFORGE_API_KEY"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              required
              minLength={32}
            />
            <div className="form-note">
              <LockKeyhole size={14} />
              Kept in memory. Cleared when you reload or disconnect.
            </div>
            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}
            <button className="button primary full" disabled={busy}>
              {busy ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <Zap size={15} />
              )}
              Connect to control plane
            </button>
          </form>
        </Modal>
      )}
      {createOpen && api && (
        <RunModal
          api={api}
          agents={agents}
          providers={providers}
          onClose={() => setCreateOpen(false)}
          onCreated={(run) => {
            setCreateOpen(false);
            openRun(run.id);
            void refresh();
          }}
        />
      )}
      {agentOpen && api && (
        <AgentModal
          api={api}
          onClose={() => setAgentOpen(false)}
          onCreated={() => {
            setAgentOpen(false);
            void refresh();
          }}
        />
      )}
    </div>
  );
}
