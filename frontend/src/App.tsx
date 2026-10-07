import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Activity, ArrowDownLeft, ArrowRight, ArrowUpRight, Box, Check, CheckCircle2, ChevronDown, ChevronRight, Circle, Clock3, Code2, Cpu, Database, FileCode2, Fingerprint, FlaskConical, GitBranch, Layers3, LayoutDashboard, LoaderCircle, LockKeyhole, Play, Plus, Radio, RefreshCw, RotateCcw, Search, Server, ShieldCheck, Terminal, Unplug, Workflow, X, XCircle, Zap } from 'lucide-react'
import { API, type Agent, type Event, type Provider, type Run, type Step, type System, type Trace } from './api'

type Page = 'Overview' | 'Runs' | 'Agents' | 'Providers' | 'System health'
const terminal = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT'])
const money = (micro: number) => `$${(micro / 1e6).toFixed(4)}`
const duration = (ms: number) => ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`
const time = (epoch: number) => new Date(epoch * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

function Badge({ status }: { status: string }) {
  return <span className={`badge ${status.toLowerCase()}`}><span className="status-dot" />{status.replaceAll('_', ' ').toLowerCase()}</span>
}
function Empty({ title, children, icon = <Workflow size={27} /> }: { title: string; children: ReactNode; icon?: ReactNode }) {
  return <div className="empty"><div className="empty-icon">{icon}</div><h3>{title}</h3><p>{children}</p></div>
}

export default function App() {
  const [page, setPage] = useState<Page>('Overview')
  const [api, setAPI] = useState<API | null>(null)
  const [key, setKey] = useState('')
  const [connectOpen, setConnectOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [agentOpen, setAgentOpen] = useState(false)
  const [runs, setRuns] = useState<Run[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [system, setSystem] = useState<System | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [trace, setTrace] = useState<Trace | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [tab, setTab] = useState('Timeline')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('All statuses')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [lastSync, setLastSync] = useState<number | null>(null)

  const refresh = useCallback(async () => {
    if (!api) return
    try {
      const [r, a] = await Promise.all([api.runs(), api.agents()])
      setRuns(r); setAgents(a); setLastSync(Date.now()); setError('')
      if (selected) {
        const [t, e] = await Promise.all([api.trace(selected), api.events(selected)])
        setTrace(t); setEvents(e)
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'Connection failed') }
  }, [api, selected])

  useEffect(() => { void refresh(); const handle = setInterval(() => void refresh(), 4000); return () => clearInterval(handle) }, [refresh])
  useEffect(() => { if (api) Promise.all([api.providers(), api.system()]).then(([p, s]) => { setProviders(p); setSystem(s) }).catch(e => setError(String(e))) }, [api])

  async function connect(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    const client = new API(key)
    try { await client.system(); setAPI(client); setKey(''); setConnectOpen(false) }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to connect') }
    finally { setBusy(false) }
  }
  async function operate(action: () => Promise<unknown>) {
    setBusy(true); setError('')
    try { await action(); await refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Request failed') }
    finally { setBusy(false) }
  }
  function navigate(next: Page) { setPage(next); setSelected(null); setTrace(null); setSearch('') }
  function openRun(id: string) { setSelected(id); setTrace(null); setPage('Runs'); setTab('Timeline') }
  function disconnect() { setAPI(null); setRuns([]); setAgents([]); setProviders([]); setSystem(null); setTrace(null); setSelected(null); setLastSync(null) }

  const active = runs.filter(r => !terminal.has(r.status)).length
  const completed = runs.filter(r => r.status === 'COMPLETED').length
  const finished = runs.filter(r => terminal.has(r.status))
  const success = finished.length ? Math.round(completed / finished.length * 100) : 0
  const totalCost = runs.reduce((sum, r) => sum + r.spent_microusd, 0)
  const latencies = runs.filter(r => terminal.has(r.status)).map(r => (r.updated_at - r.created_at) * 1000).sort((a, b) => a - b)
  const p50 = latencies.length ? latencies[Math.floor(latencies.length / 2)] : null
  const visibleRuns = runs.filter(r => (filter === 'All statuses' || r.status === filter) && `${r.id} ${r.task}`.toLowerCase().includes(search.toLowerCase()))
  const agentById = Object.fromEntries(agents.map(a => [a.id, a]))

  return <div className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => navigate('Overview')}><span className="brand-mark"><Layers3 size={22} strokeWidth={2.4} /></span>agentforge<span className="brand-period">.</span></button>
      <div className="workspace"><div className="workspace-avatar">AF</div><div><strong>Development</strong><span>Execution workspace</span></div><ChevronDown size={14} /></div>
      <div className="nav-label">CONTROL PLANE</div>
      <nav>{([['Overview', LayoutDashboard], ['Runs', Workflow], ['Agents', Box], ['Providers', GitBranch], ['System health', Activity]] as const).map(([name, Icon]) => <button key={name} className={`nav-item ${page === name ? 'selected' : ''}`} onClick={() => navigate(name)}><Icon size={18} /><span>{name}</span>{name === 'Runs' && active > 0 && <small>{active}</small>}</button>)}</nav>
      <div className="sidebar-note"><div><ShieldCheck size={17} /><span>Built for the failure path</span></div><p>Fenced leases. Durable checkpoints. Observable execution.</p><a href="/api/docs" target="_blank" rel="noreferrer">Explore the API <ArrowUpRight size={13} /></a></div>
      <div className="sidebar-bottom"><span className={`connection-dot ${api ? 'online' : ''}`} /><span>{api ? 'Workspace connected' : 'Workspace disconnected'}</span><button aria-label={api ? 'Disconnect' : 'Connect workspace'} onClick={() => api ? disconnect() : setConnectOpen(true)}><Unplug size={15} /></button></div>
      <div className="version">AGENTFORGE <span>v0.1.0</span></div>
    </aside>

    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>{page}</strong>{selected && <><ChevronRight size={13} /><code>{selected.slice(0, 8)}</code></>}</div><div className="topbar-right"><span className="environment"><span />{system?.environment || 'Local environment'}</span><button className="icon-button" title="Refresh" onClick={() => void refresh()}><RefreshCw size={16} /></button><button className="avatar" onClick={() => setConnectOpen(true)} aria-label="Connection settings">AF</button></div></header>
      <main>
        {error && !connectOpen && <div className="error-banner" role="alert"><XCircle size={16} />{error}<button onClick={() => setError('')} aria-label="Dismiss error"><X size={14} /></button></div>}
        {selected ? <>
          <button className="back-link" onClick={() => { setSelected(null); setTrace(null) }}>← All runs</button>
          <div className="page-heading"><div><div className="eyebrow">EXECUTION TRACE</div><h1>Repository repair <span className="heading-id">/{selected.slice(0, 8)}</span></h1><p>{trace?.run.task || 'Loading execution state…'}</p></div><div className="heading-actions">{trace && <Badge status={trace.run.status} />}{trace && !terminal.has(trace.run.status) && <button className="button secondary" disabled={busy} onClick={() => void operate(() => api!.cancel(selected))}><X size={15} />Cancel run</button>}{trace && terminal.has(trace.run.status) && trace.run.status !== 'COMPLETED' && <button className="button secondary" disabled={busy} onClick={() => void operate(async () => { const r = await api!.retry(selected); openRun(r.id) })}><RotateCcw size={15} />Retry as new run</button>}</div></div>
          {trace ? <>
            <div className="run-summary"><Summary label="Agent version" value={`${agentById[trace.run.agent_id]?.name || 'agent'} / ${agentById[trace.run.agent_id]?.version || '—'}`} icon={<Box size={16} />} /><Summary label="Elapsed" value={duration((trace.run.updated_at - trace.run.created_at) * 1000)} icon={<Clock3 size={16} />} /><Summary label="Charged usage" value={`${trace.run.charged_tokens.toLocaleString()} tokens`} icon={<Cpu size={16} />} /><Summary label="Estimated spend" value={money(trace.run.spent_microusd)} icon={<Fingerprint size={16} />} /></div>
            {trace.run.error_type && <div className="error-banner"><XCircle size={16} />{trace.run.error_type}</div>}
            <div className="trace-layout"><section className="panel trace-panel"><div className="tabs">{['Timeline', 'Events', 'Checkpoint'].map(t => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}{t === 'Timeline' && <span>{trace.steps.length}</span>}</button>)}</div>
              {tab === 'Timeline' && <div className="timeline">{trace.steps.map(step => <StepRow key={step.id} step={step} expanded={expanded === step.id} onClick={() => setExpanded(expanded === step.id ? null : step.id)} />)}{!trace.steps.length && <Empty title="Waiting for a worker">The run is safely queued in the database.</Empty>}<div className="timeline-end"><span className={`timeline-node ${trace.run.status === 'COMPLETED' ? 'done' : ''}`}><Check size={13} /></span><strong>{terminal.has(trace.run.status) ? trace.run.status.replaceAll('_', ' ').toLowerCase() : 'Execution in progress'}</strong></div></div>}
              {tab === 'Events' && <div className="event-list">{events.map(event => <div key={event.id}><code>{time(event.at)}</code><span>{event.kind}</span><pre>{JSON.stringify(event.data, null, 2)}</pre></div>)}</div>}
              {tab === 'Checkpoint' && <div className="checkpoint"><div className="checkpoint-heading"><Database size={17} /><strong>Checkpoint {trace.checkpoint?.sequence ?? 0}</strong><span>schema v{trace.checkpoint?.schema_version ?? 1}</span></div><p>Committed atomically with step completion. Recovery resumes after this checkpoint.</p>{Object.entries(trace.checkpoint?.payload.files || {}).map(([name, source]) => <div className="source-file" key={name}><div><FileCode2 size={14} />{name}</div><pre>{source}</pre></div>)}</div>}
            </section><aside className="run-aside"><section className="panel"><div className="panel-heading"><h3>Run contract</h3><LockKeyhole size={15} /></div><dl><dt>Run ID</dt><dd className="mono wrap">{selected}</dd><dt>Repository fixture</dt><dd>{trace.run.fixture}</dd><dt>Checkpoint</dt><dd>{trace.run.checkpoint_seq} committed steps</dd><dt>Worker recoveries</dt><dd>{trace.run.recoveries}</dd><dt>Deadline</dt><dd>{time(trace.run.deadline)}</dd><dt>Verification</dt><dd className={trace.checkpoint?.payload.tests_passed ? 'text-green' : ''}>{trace.checkpoint?.payload.tests_passed ? 'Regression tests passed' : 'Awaiting passing tests'}</dd></dl></section><section className="panel"><div className="panel-heading"><h3>Agent output</h3><Terminal size={15} /></div><p className="agent-output">{trace.run.output || 'The final explanation appears when execution completes.'}</p></section><div className="security-caption"><ShieldCheck size={15} />Tool code runs in disposable containers with network access disabled.</div></aside></div>
          </> : <div className="loading"><LoaderCircle className="spin" size={24} />Loading trace…</div>}
        </> : <>
          <div className="page-heading"><div><div className="eyebrow">AGENT EXECUTION PLATFORM</div><h1>{page === 'Overview' ? 'Every run, accounted for.' : page === 'Runs' ? 'Execution runs' : page === 'Agents' ? 'Your agent fleet' : page === 'Providers' ? 'Model routing' : 'System health'}</h1><p>{page === 'Overview' ? 'Inspect the work. Understand the failures. Resume with confidence.' : page === 'Runs' ? 'Durable jobs, from submission through the last checkpoint.' : page === 'Agents' ? 'Immutable configurations. Explicit limits. Reproducible behavior.' : page === 'Providers' ? 'Provider-neutral execution with visible, rules-based decisions.' : 'The dependencies behind reliable agent execution.'}</p></div><button className="button primary" onClick={() => api ? setCreateOpen(true) : setConnectOpen(true)}><Plus size={16} />{api ? 'New run' : 'Connect workspace'}</button></div>
          {(page === 'Overview' || page === 'Runs') && <>
            <div className="stats-grid"><Stat label="TOTAL RUNS" value={api ? String(runs.length) : '—'} note="Most recent 100 executions" icon={<Workflow size={18} />} /><Stat label="SUCCESS RATE" value={api && finished.length ? `${success}%` : '—'} note={`${completed} completed · ${finished.length} terminal`} icon={<CheckCircle2 size={18} />} /><Stat label="MEDIAN LATENCY" value={p50 === null ? '—' : duration(p50)} note="End-to-end · terminal runs" icon={<Clock3 size={18} />} /><Stat label="ESTIMATED SPEND" value={api ? money(totalCost) : '—'} note="Includes ambiguous reservations" icon={<Cpu size={18} />} /></div>
            {page === 'Overview' && <div className="overview-strip"><div className="strip-icon"><Radio size={19} /></div><div><strong>{active ? `${active} run${active > 1 ? 's' : ''} in flight` : api ? 'Ready for your next execution' : 'Your runtime, in one place'}</strong><span>{api ? 'Every completed step is saved before the next one starts.' : 'Connect to your control plane to see live runs and execution traces.'}</span></div><span className="strip-tag"><Database size={13} />Durable by design</span></div>}
            <section className="panel runs-panel"><div className="panel-heading"><div className="section-title"><h2>{page === 'Overview' ? 'Recent runs' : 'All runs'}</h2><span className="count">{runs.length}</span></div><div className="live-label"><span className={api ? 'online' : ''} />{api ? 'Live · 4s refresh' : 'Awaiting connection'}</div></div><div className="table-toolbar"><div className="search-input"><Search size={15} /><input aria-label="Search runs" placeholder="Search by run ID or task…" value={search} onChange={e => setSearch(e.target.value)} /><kbd>/</kbd></div><select aria-label="Filter by status" value={filter} onChange={e => setFilter(e.target.value)}>{['All statuses', 'QUEUED', 'RUNNING', 'RETRYING', 'COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT'].map(s => <option key={s}>{s}</option>)}</select></div>
              {visibleRuns.length ? <div className="table-scroll"><table><thead><tr><th>RUN / TASK</th><th>AGENT</th><th>STATUS</th><th>STEPS</th><th>LATENCY</th><th>COST</th><th /></tr></thead><tbody>{visibleRuns.map(run => <tr key={run.id} onClick={() => openRun(run.id)} tabIndex={0} onKeyDown={e => e.key === 'Enter' && openRun(run.id)}><td><div className="run-cell"><span className="run-icon"><GitBranch size={15} /></span><div><strong>{run.task}</strong><code>{run.id.slice(0, 8)} <span>·</span> {time(run.created_at)}</code></div></div></td><td><span className="agent-name">{agentById[run.agent_id]?.name || 'agent'}</span><small className="table-sub">{agentById[run.agent_id]?.version || '—'}</small></td><td><Badge status={run.status} /></td><td className="mono">{run.checkpoint_seq}</td><td className="mono">{duration((run.updated_at - run.created_at) * 1000)}</td><td className="mono">{money(run.spent_microusd)}</td><td><ArrowUpRight size={15} /></td></tr>)}</tbody></table></div> : <Empty title={!api ? 'Connect your execution workspace' : search || filter !== 'All statuses' ? 'No matching runs' : 'Your first run starts here'}>{!api ? 'Your runs, traces, and checkpoints will appear here. Your API key stays in memory for this session.' : search || filter !== 'All statuses' ? 'Try a different search or status filter.' : <><span>Launch the Repository Engineer to inspect, repair, and verify a broken sample.</span><button className="button secondary" onClick={() => setCreateOpen(true)}><Play size={14} />Launch a run</button></>}</Empty>}
              <div className="table-footer"><span>{visibleRuns.length} executions shown</span><span>{lastSync ? `Last synced ${new Date(lastSync).toLocaleTimeString()}` : 'No execution data loaded'}<ShieldCheck size={12} /></span></div></section>
            {page === 'Overview' && <div className="bottom-grid"><section className="feature-panel"><div className="feature-label"><Code2 size={15} />DEVELOPER FIRST</div><h3>One API. A durable execution.</h3><p>Submit a task once. Follow its state through failures, retries, and recovery.</p><pre><span>client</span>.run(agent=agent,{"\n"}    task=<em>"Repair the failing tests"</em>)</pre><a href="/api/docs" target="_blank" rel="noreferrer">Open API reference <ArrowRight size={14} /></a></section><section className="feature-panel guarantee-panel"><div className="feature-label"><ShieldCheck size={15} />EXECUTION GUARANTEES</div><div className="guarantee"><Check size={15} /><span>Atomic step + checkpoint commits</span></div><div className="guarantee"><Check size={15} /><span>Stale workers cannot commit results</span></div><div className="guarantee"><Check size={15} /><span>Bounded retries and spend admission</span></div><div className="guarantee"><Check size={15} /><span>Isolated, resource-limited tool execution</span></div><div className="semantics">At-least-once execution · Fenced commits</div></section></div>}
          </>}
          {page === 'Agents' && <section className="panel"><div className="panel-heading"><h2>Registered agents <span className="count">{agents.length}</span></h2><button className="button secondary" onClick={() => api ? setAgentOpen(true) : setConnectOpen(true)}><Plus size={14} />Register agent</button></div>{agents.length ? <div className="agent-grid">{agents.map(a => <div className="agent-card" key={a.id}><div className="agent-card-top"><span className="agent-box"><Box size={22} /></span><span className="version-tag">{a.version}</span></div><h3>{a.name}</h3><p>{a.config.instructions}</p><div className="agent-limits"><span><Cpu size={13} />{a.config.provider}</span><span><Clock3 size={13} />{a.config.timeout}s</span><span>{a.config.max_steps} steps</span></div><div className="agent-card-footer"><code>{a.id.slice(0, 8)}</code><button onClick={() => setCreateOpen(true)}>Run agent <ArrowUpRight size={14} /></button></div></div>)}</div> : <Empty title="Give your runtime its first agent" icon={<Box size={27} />}>Register an immutable agent configuration or launch a run to create the default Repository Engineer.</Empty>}</section>}
          {page === 'Providers' && <><div className="notice"><GitBranch size={17} /><div><strong>Simple routing. Visible decisions.</strong><p>Auto routing chooses the lowest estimated cost within budget, then prefers providers with fewer failed attempts. Every decision is recorded in the trace.</p></div></div><div className="provider-grid">{providers.length ? providers.map(p => <section className="panel provider-card" key={p.provider}><div className="provider-symbol"><Cpu size={23} /></div><div className="provider-heading"><h3>{p.provider === 'demo' ? 'Deterministic demo' : p.provider === 'openai' ? 'OpenAI' : 'Google Gemini'}</h3><span className={`config-tag ${p.configured ? 'enabled' : ''}`}>{p.configured ? 'Configured' : 'Not configured'}</span></div><code>{p.model}</code><p>{p.provider === 'demo' ? 'Scripted fixture planner. No model inference, token usage, or provider cost.' : 'Live provider adapter. Availability is established by actual requests; configuration alone is not a health check.'}</p><div className="provider-footer"><Circle size={11} />{p.health === 'fixture' ? 'Reproducible fixture' : 'Health not probed'}</div></section>) : <Empty title="Connect to inspect providers" icon={<GitBranch size={27} />}>Provider keys are configured on the server.</Empty>}</div></>}
          {page === 'System health' && <div className="health-grid"><Health icon={<Server />} name="API / control plane" value={api ? 'Connected' : 'Disconnected'} detail="Authenticated REST API · automatic OpenAPI" good={!!api} /><Health icon={<Database />} name="Durable queue" value={system?.queue || 'Unknown'} detail="Runs, leases, events, and checkpoints share one database." good={!!system} /><Health icon={<ShieldCheck />} name="Tool isolation" value={system?.sandbox || 'Unknown'} detail="Sandbox readiness is enforced by worker startup dependencies." good={!!system} /><Health icon={<Activity />} name="Execution semantics" value="At least once" detail="Only a worker holding the current lease can commit." good={true} /></div>}
        </>}
        <footer className="page-footer"><span>AgentForge / execution control plane</span><span>Designed for observable, recoverable work <ArrowDownLeft size={12} /></span></footer>
      </main>
    </div>

    {connectOpen && <Modal title="Connect your workspace" subtitle="Use the API key from your server environment." onClose={() => setConnectOpen(false)}><form onSubmit={connect}><label htmlFor="api-key">API KEY</label><input id="api-key" type="password" autoFocus autoComplete="off" spellCheck={false} placeholder="Paste AGENTFORGE_API_KEY" value={key} onChange={e => setKey(e.target.value)} required minLength={32} /><div className="form-note"><LockKeyhole size={14} />Kept in memory. Cleared when you reload or disconnect.</div>{error && <div className="form-error" role="alert">{error}</div>}<button className="button primary full" disabled={busy}>{busy ? <LoaderCircle className="spin" size={15} /> : <Zap size={15} />}Connect to control plane</button></form></Modal>}
    {createOpen && api && <RunModal api={api} agents={agents} providers={providers} onClose={() => setCreateOpen(false)} onCreated={run => { setCreateOpen(false); openRun(run.id); void refresh() }} />}
    {agentOpen && api && <AgentModal api={api} onClose={() => setAgentOpen(false)} onCreated={() => { setAgentOpen(false); void refresh() }} />}
  </div>
}

function Stat({ label, value, note, icon }: { label: string; value: string; note: string; icon: ReactNode }) {
  return <section className="stat"><div className="stat-top"><span>{label}</span>{icon}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></section>
}
function Summary({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return <div><span>{icon}{label}</span><strong>{value}</strong></div>
}
function StepRow({ step, expanded, onClick }: { step: Step; expanded: boolean; onClick: () => void }) {
  const isModel = step.kind === 'model'
  const failed = step.status === 'FAILED' || step.status === 'UNKNOWN'
  const title = isModel ? 'Model decision' : (step.detail.operation || 'Tool execution').replaceAll('_', ' ')
  return <div className={`timeline-step ${failed ? 'step-failed' : ''}`}><span className={`timeline-node ${failed ? 'failed' : step.status === 'SUCCEEDED' ? 'done' : ''}`}>{failed ? <X size={12} /> : isModel ? <Cpu size={12} /> : <Terminal size={12} />}</span><button className="step-header" onClick={onClick}><div><div className="step-title"><strong>{title}</strong>{step.attempt > 1 && <span className="attempt">attempt {step.attempt}</span>}<code>{isModel ? step.model : step.detail.path || 'sandbox'}</code></div><p>{step.error_type || (isModel ? step.routing_reason : step.detail.exit_code !== undefined ? `Exit code ${step.detail.exit_code} · isolated container` : 'Executing operation')}</p></div><span className="step-duration">{step.duration_ms === null ? 'in flight' : duration(step.duration_ms)}</span><ChevronDown size={14} className={expanded ? 'rotate' : ''} /></button>{expanded && <div className="step-detail">{step.detail.action && <p>{step.detail.action.explanation}</p>}{step.detail.stdout && <><label>STDOUT</label><pre>{step.detail.stdout}</pre></>}{step.detail.stderr && <><label>STDERR</label><pre>{step.detail.stderr}</pre></>}{isModel && <div className="step-usage"><span>{step.tokens} tokens</span><span>{money(step.cost_microusd)}</span><span>{step.provider}</span></div>}{step.detail.action?.content && <pre>{step.detail.action.content}</pre>}</div>}</div>
}
function Health({ icon, name, value, detail, good }: { icon: ReactNode; name: string; value: string; detail: string; good: boolean }) {
  return <section className="panel health-card"><div>{icon}<span className={`connection-dot ${good ? 'online' : ''}`} /></div><h3>{name}</h3><strong>{value}</strong><p>{detail}</p></section>
}
function Modal({ title, subtitle, onClose, children }: { title: string; subtitle: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => { const close = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }; document.addEventListener('keydown', close); return () => document.removeEventListener('keydown', close) }, [onClose])
  return <div className="modal-backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}><section className="modal" role="dialog" aria-modal="true" aria-label={title}><button className="modal-close icon-button" aria-label="Close dialog" onClick={onClose}><X size={18} /></button><span className="modal-icon"><Workflow size={23} /></span><h2>{title}</h2><p>{subtitle}</p>{children}</section></div>
}
function RunModal({ api, agents, providers, onClose, onCreated }: { api: API; agents: Agent[]; providers: Provider[]; onClose: () => void; onCreated: (r: Run) => void }) {
  const [agentId, setAgentId] = useState(agents[0]?.id || '')
  const [fixture, setFixture] = useState('mean')
  const [provider, setProvider] = useState('demo')
  const [task, setTask] = useState('Inspect the bundled repository, repair the bug, and verify the original tests.')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true)
    try {
      let id = agentId
      if (!id) { const agent = await api.request<Agent>('/v1/agents', { name: `repo-engineer-${provider}`, provider }); id = agent.id }
      const run = await api.request<Run>('/v1/runs', { agent_id: id, task, fixture }, true)
      onCreated(run)
    } catch (e) { setError(e instanceof Error ? e.message : 'Submission failed'); setBusy(false) }
  }
  const selectedProvider = agents.find(a => a.id === agentId)?.config.provider || provider
  return <Modal title="Launch an execution" subtitle="A bounded repository repair, with a complete trace." onClose={onClose}><form onSubmit={submit}><label htmlFor="agent">AGENT CONFIGURATION</label><select id="agent" value={agentId} onChange={e => setAgentId(e.target.value)}><option value="">Create default Repository Engineer</option>{agents.map(a => <option key={a.id} value={a.id}>{a.name} / {a.version} · {a.config.provider}</option>)}</select>{!agentId && <><label htmlFor="provider">PLANNER</label><select id="provider" value={provider} onChange={e => setProvider(e.target.value)}><option value="demo">Deterministic demo · no LLM</option>{providers.filter(p => p.configured && p.provider !== 'demo').map(p => <option key={p.provider} value={p.provider}>{p.provider} · {p.model}</option>)}{providers.some(p => p.configured && p.provider !== 'demo') && <option value="auto">Auto · lowest estimated cost + fallback</option>}</select></>}<label htmlFor="fixture">REPOSITORY FIXTURE</label><select id="fixture" value={fixture} onChange={e => setFixture(e.target.value)}><option value="mean">Statistics · incorrect mean</option><option value="clamp">Statistics · boundary clamp</option></select><label htmlFor="task">TASK</label><textarea id="task" value={task} onChange={e => setTask(e.target.value)} required maxLength={4000} rows={3} /><div className="form-note"><FlaskConical size={15} />{selectedProvider === 'demo' ? 'Scripted planner. Tests still execute in real isolated containers.' : 'Live model inference. Source and tool results are sent to the selected provider.'}</div>{error && <div className="form-error" role="alert">{error}</div>}<button className="button primary full" disabled={busy}>{busy ? <LoaderCircle className="spin" size={15} /> : <Play size={15} />}Submit run</button></form></Modal>
}
function AgentModal({ api, onClose, onCreated }: { api: API; onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('repo-engineer')
  const [version, setVersion] = useState('v1')
  const [provider, setProvider] = useState('demo')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true)
    try { await api.request('/v1/agents', { name, version, provider }); onCreated() }
    catch (e) { setError(e instanceof Error ? e.message : 'Registration failed'); setBusy(false) }
  }
  return <Modal title="Register an agent" subtitle="Agent versions are immutable. Register a new version to change behavior." onClose={onClose}><form onSubmit={submit}><label htmlFor="name">NAME</label><input id="name" value={name} onChange={e => setName(e.target.value)} required maxLength={80} /><label htmlFor="version">VERSION</label><input id="version" value={version} onChange={e => setVersion(e.target.value)} required maxLength={32} /><label htmlFor="agent-provider">PROVIDER POLICY</label><select id="agent-provider" value={provider} onChange={e => setProvider(e.target.value)}>{['demo', 'auto', 'openai', 'gemini'].map(p => <option key={p}>{p}</option>)}</select><div className="form-note"><ShieldCheck size={15} />Defaults: 120s timeout · $0.20 budget · 16 steps</div>{error && <div className="form-error" role="alert">{error}</div>}<button className="button primary full" disabled={busy}><Plus size={15} />Register immutable version</button></form></Modal>
}
