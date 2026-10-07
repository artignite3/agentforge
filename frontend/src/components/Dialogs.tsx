import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  X,
  Workflow,
  LoaderCircle,
  Play,
  FlaskConical,
  ShieldCheck,
  Plus,
} from "lucide-react";
import { API, type Agent, type Run, type Provider } from "../api";
export function Modal({
  title,
  subtitle,
  onClose,
  children,
}: {
  title: string;
  subtitle: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [onClose]);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <button
          className="modal-close icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={18} />
        </button>
        <span className="modal-icon">
          <Workflow size={23} />
        </span>
        <h2>{title}</h2>
        <p>{subtitle}</p>
        {children}
      </section>
    </div>
  );
}
export function RunModal({
  api,
  agents,
  providers,
  onClose,
  onCreated,
}: {
  api: API;
  agents: Agent[];
  providers: Provider[];
  onClose: () => void;
  onCreated: (r: Run) => void;
}) {
  const [agentId, setAgentId] = useState(agents[0]?.id || "");
  const [fixture, setFixture] = useState("mean");
  const [provider, setProvider] = useState("demo");
  const [task, setTask] = useState(
    "Inspect the bundled repository, repair the bug, and verify the original tests.",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      let id = agentId;
      if (!id) {
        const agent = await api.request<Agent>("/v1/agents", {
          name: `repo-engineer-${provider}`,
          provider,
        });
        id = agent.id;
      }
      const run = await api.request<Run>(
        "/v1/runs",
        { agent_id: id, task, fixture },
        true,
      );
      onCreated(run);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
      setBusy(false);
    }
  }
  const selectedProvider =
    agents.find((a) => a.id === agentId)?.config.provider || provider;
  return (
    <Modal
      title="Launch an execution"
      subtitle="A bounded repository repair, with a complete trace."
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <label htmlFor="agent">AGENT CONFIGURATION</label>
        <select
          id="agent"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
        >
          <option value="">Create default Repository Engineer</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} / {a.version} · {a.config.provider}
            </option>
          ))}
        </select>
        {!agentId && (
          <>
            <label htmlFor="provider">PLANNER</label>
            <select
              id="provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              <option value="demo">Deterministic demo · no LLM</option>
              {providers
                .filter((p) => p.configured && p.provider !== "demo")
                .map((p) => (
                  <option key={p.provider} value={p.provider}>
                    {p.provider} · {p.model}
                  </option>
                ))}
              {providers.some((p) => p.configured && p.provider !== "demo") && (
                <option value="auto">
                  Auto · lowest estimated cost + fallback
                </option>
              )}
            </select>
          </>
        )}
        <label htmlFor="fixture">REPOSITORY FIXTURE</label>
        <select
          id="fixture"
          value={fixture}
          onChange={(e) => setFixture(e.target.value)}
        >
          <option value="mean">Statistics · incorrect mean</option>
          <option value="clamp">Statistics · boundary clamp</option>
        </select>
        <label htmlFor="task">TASK</label>
        <textarea
          id="task"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          required
          maxLength={4000}
          rows={3}
        />
        <div className="form-note">
          <FlaskConical size={15} />
          {selectedProvider === "demo"
            ? "Scripted planner. Tests still execute in real isolated containers."
            : "Live model inference. Source and tool results are sent to the selected provider."}
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
            <Play size={15} />
          )}
          Submit run
        </button>
      </form>
    </Modal>
  );
}
export function AgentModal({
  api,
  onClose,
  onCreated,
}: {
  api: API;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("repo-engineer");
  const [version, setVersion] = useState("v1");
  const [provider, setProvider] = useState("demo");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.request("/v1/agents", { name, version, provider });
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed");
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Register an agent"
      subtitle="Agent versions are immutable. Register a new version to change behavior."
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <label htmlFor="name">NAME</label>
        <input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          maxLength={80}
        />
        <label htmlFor="version">VERSION</label>
        <input
          id="version"
          value={version}
          onChange={(e) => setVersion(e.target.value)}
          required
          maxLength={32}
        />
        <label htmlFor="agent-provider">PROVIDER POLICY</label>
        <select
          id="agent-provider"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          {["demo", "auto", "openai", "gemini"].map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <div className="form-note">
          <ShieldCheck size={15} />
          Defaults: 120s timeout · $0.20 budget · 16 steps
        </div>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        <button className="button primary full" disabled={busy}>
          <Plus size={15} />
          Register immutable version
        </button>
      </form>
    </Modal>
  );
}
