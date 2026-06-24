export type ShowProject = {
  id: number;
  name: string;
  description: string;
  agent_count?: number;
  created_at: string;
  updated_at: string;
};

export type Agent = {
  id: number;
  name: string;
  type: string;
  model_provider: string | null;
  model_name: string | null;
  config: Record<string, unknown>;
  data_source_id: number | null;
  show_project_id: number | null;
  created_at: string;
  updated_at: string;
};

export type DataSource = {
  id: number;
  name: string;
  type: string;
  location: string | null;
  status: string;
  created_at: string;
};

export type AgentPatch = Partial<{
  name: string;
  type: string;
  model_provider: string;
  model_name: string;
  config: Record<string, unknown>;
  data_source_id: number | null;
}>;

async function req(path: string, init?: RequestInit) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(String(res.status));
  return res.status === 204 ? null : res.json();
}

export const api = {
  me: (): Promise<{ username: string }> => req("/api/me"),
  logout: () => req("/api/logout", { method: "POST" }),
  listProjects: (): Promise<ShowProject[]> => req("/api/projects"),
  createProject: (name: string, description = ""): Promise<ShowProject> =>
    req("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  getProject: (id: number): Promise<ShowProject> => req(`/api/projects/${id}`),
  deleteProject: (id: number) => req(`/api/projects/${id}`, { method: "DELETE" }),
  listAgents: (projectId: number): Promise<Agent[]> =>
    req(`/api/agents?project_id=${projectId}`),
  createAgent: (
    name: string,
    type: string,
    projectId: number,
  ): Promise<Agent> =>
    req("/api/agents", {
      method: "POST",
      body: JSON.stringify({ name, type, show_project_id: projectId }),
    }),
  getAgent: (id: number): Promise<Agent> => req(`/api/agents/${id}`),
  updateAgent: (id: number, patch: AgentPatch): Promise<Agent> =>
    req(`/api/agents/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteAgent: (id: number) => req(`/api/agents/${id}`, { method: "DELETE" }),
  listDataSources: (projectId: number): Promise<DataSource[]> =>
    req(`/api/data-sources?project_id=${projectId}`),
  uploadDataSource: async (
    file: File,
    projectId: number,
  ): Promise<DataSource & { records: number }> => {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(`/api/data-sources?project_id=${projectId}`, {
      method: "POST",
      body,
    });
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  },
  buildAgentOntology: (
    agentId: number,
    dataSourceId: number,
  ): Promise<OntologySummary> =>
    req(`/api/agents/${agentId}/build`, {
      method: "POST",
      body: JSON.stringify({ data_source_id: dataSourceId }),
    }),
  getOntology: (projectId: number): Promise<Ontology> =>
    req(`/api/ontology?project_id=${projectId}`),
  getMessages: (agentId: number): Promise<ChatMessage[]> =>
    req(`/api/agents/${agentId}/messages`),
  chat: (agentId: number, content: string): Promise<ChatReply> =>
    req(`/api/agents/${agentId}/chat`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
};

export type Traversal = { nodes: string[]; edges: { from: string; to: string; type: string }[] };

export type Artifact =
  | { type: "bar"; title?: string; data: { label: string; value: number }[] }
  | { type: "line"; title?: string; data: { label: string; value: number }[] }
  | { type: "metrics"; title?: string; items: { label: string; value: string | number }[] }
  | { type: "table"; title?: string; columns: string[]; rows: (string | number)[][] }
  | { type: "map"; title?: string; points: { lat: number; lng: number; label?: string }[] };

export type ChatMessage = {
  role: string;
  content: string;
  metadata: { traversal?: Traversal; artifact?: Artifact | null };
  created_at: string;
};

export type ChatReply = {
  content: string;
  traversal: Traversal;
  artifact: Artifact | null;
};

export type OntologyNode = { uid: string; label: string; source_id: number | null };
export type OntologyEdge = { from: string; to: string; type: string };
export type Ontology = {
  classes: string[];
  relations: string[];
  nodes: OntologyNode[];
  edges: OntologyEdge[];
};

export type OntologySummary = {
  classes: number;
  relations: number;
  nodes: number;
  edges: number;
  method?: string;
};

export const MODELS: Record<string, string[]> = {
  claude: ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"],
  openai: ["gpt-4o", "gpt-4o-mini", "o3"],
};
