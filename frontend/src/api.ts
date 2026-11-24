export interface Run {
  id: string;
  agent_id: string;
  task: string;
  fixture: string;
  status: string;
  created_at: number;
  updated_at: number;
  deadline: number;
  checkpoint_seq: number;
  spent_microusd: number;
  charged_tokens: number;
  recoveries: number;
  output: string | null;
  error_type: string | null;
}
export interface Agent {
  id: string;
  name: string;
  version: string;
  config: {
    provider: string;
    timeout: number;
    budget_usd: number;
    max_steps: number;
    instructions: string;
  };
}
export interface Step {
  id: string;
  sequence: number;
  attempt: number;
  kind: string;
  status: string;
  started_at: number;
  duration_ms: number | null;
  provider: string | null;
  model: string | null;
  routing_reason: string | null;
  error_type: string | null;
  cost_microusd: number;
  tokens: number;
  detail: {
    operation?: string;
    path?: string;
    stdout?: string;
    stderr?: string;
    exit_code?: number;
    action?: { operation: string; explanation: string; content: string };
    input_tokens?: number;
    output_tokens?: number;
  };
}
export interface Trace {
  run: Run;
  steps: Step[];
  checkpoint: {
    sequence: number;
    schema_version: number;
    payload: { files: Record<string, string>; tests_passed: boolean };
  } | null;
}
export interface Event {
  id: number;
  kind: string;
  at: number;
  data: Record<string, unknown>;
}
export interface Provider {
  provider: string;
  model: string;
  configured: boolean;
  health: string;
}
export interface System {
  environment: string;
  queue: string;
  semantics: string;
  sandbox: string;
  sandbox_ready: boolean;
}

export class API {
  constructor(private key: string) {}
  async request<T>(
    path: string,
    body?: unknown,
    idempotent = false,
  ): Promise<T> {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.key}`,
    };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (idempotent) headers["Idempotency-Key"] = crypto.randomUUID();
    const response = await fetch(`/api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(10000),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok)
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : `Request rejected (${response.status})`,
      );
    return data as T;
  }
  runs() {
    return this.request<Run[]>("/v1/runs");
  }
  agents() {
    return this.request<Agent[]>("/v1/agents");
  }
  providers() {
    return this.request<Provider[]>("/v1/providers");
  }
  system() {
    return this.request<System>("/v1/system");
  }
  trace(id: string) {
    return this.request<Trace>(`/v1/runs/${id}/trace`);
  }
  events(id: string, after = 0) {
    return this.request<Event[]>(`/v1/runs/${id}/events?after=${after}`);
  }
  cancel(id: string) {
    return this.request<Run>(`/v1/runs/${id}/cancel`, {});
  }
  retry(id: string) {
    return this.request<Run>(`/v1/runs/${id}/retry`, {}, true);
  }
}
