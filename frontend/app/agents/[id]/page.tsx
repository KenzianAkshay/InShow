"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Check,
  Database,
  Hammer,
  MessageSquare,
  Trash2,
  Upload,
} from "lucide-react";
import { api, Agent, DataSource, MODELS, OntologySummary } from "@/lib/api";
import AgentRibbon from "@/app/components/AgentRibbon";
import { Button } from "@/app/components/ui/button";
import { Input } from "@/app/components/ui/input";
import { Label } from "@/app/components/ui/label";
import { Select } from "@/app/components/ui/select";
import { Textarea } from "@/app/components/ui/textarea";
import { Card, CardContent } from "@/app/components/ui/card";
import { Badge } from "@/app/components/ui/badge";

export default function AgentSetup() {
  const params = useParams();
  const router = useRouter();
  const agentId = Number(params.id);

  const [agent, setAgent] = useState<Agent | null>(null);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [provider, setProvider] = useState("claude");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [dataSourceId, setDataSourceId] = useState<number | "">("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [ontology, setOntology] = useState("");
  const [allColumns, setAllColumns] = useState(false);
  const [saved, setSaved] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [summary, setSummary] = useState<OntologySummary | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function refreshDataSources(pid: number) {
    return api.listDataSources(pid).then(setDataSources).catch(() => {});
  }

  async function upload() {
    if (!file || projectId === null) return;
    setBusy("upload");
    setNotice(null);
    try {
      const ds = await api.uploadDataSource(file, projectId);
      await refreshDataSources(projectId);
      setDataSourceId(ds.id);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setNotice(`Ingested ${ds.records} records from ${ds.name}`);
    } catch {
      setNotice("Upload failed. Use a .csv, .json, or .xlsx file.");
    } finally {
      setBusy(null);
    }
  }

  async function build() {
    if (dataSourceId === "") return;
    setBusy("build");
    setNotice(null);
    setSummary(null);
    try {
      setSummary(
        await api.buildAgentOntology(agentId, Number(dataSourceId), allColumns),
      );
    } catch {
      setNotice("Build failed. Ensure Neo4j is running.");
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    api
      .getAgent(agentId)
      .then((a) => {
        setAgent(a);
        setProvider(a.model_provider ?? "claude");
        setModel(a.model_name ?? "");
        setApiKey(String(a.config?.api_key ?? ""));
        setDataSourceId(a.data_source_id ?? "");
        setSystemPrompt(String(a.config?.system_prompt ?? ""));
        setOntology(String(a.config?.ontology_instructions ?? ""));
        setAllColumns(Boolean(a.config?.all_columns_as_nodes));
        if (a.show_project_id !== null) {
          setProjectId(a.show_project_id);
          refreshDataSources(a.show_project_id);
        }
      })
      .catch(() => router.push("/"));
  }, [agentId, router]);

  async function save() {
    const updated = await api.updateAgent(agentId, {
      model_provider: provider,
      model_name: model || MODELS[provider][0],
      data_source_id: dataSourceId === "" ? null : Number(dataSourceId),
      config: {
        system_prompt: systemPrompt,
        ontology_instructions: ontology,
        api_key: apiKey,
        all_columns_as_nodes: allColumns,
      },
    });
    setAgent(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  async function remove() {
    await api.deleteAgent(agentId);
    router.push("/");
  }

  if (!agent) return null;

  const models = MODELS[provider] ?? [];

  return (
    <main className="mx-auto max-w-2xl px-5 py-10">
      <AgentRibbon projectId={projectId} currentAgentId={agentId} />

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex items-baseline justify-between gap-4">
          <h1 className="text-3xl font-bold tracking-tight">{agent.name}</h1>
          <Link
            href={`/agents/${agentId}/chat`}
            className="inline-flex shrink-0 items-center gap-1.5 text-sm font-semibold text-accent transition-opacity hover:opacity-80"
          >
            <MessageSquare className="size-4" />
            Open chat
          </Link>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {agent.type === "ontology_creation"
            ? "Ontology Creation agent"
            : agent.type === "booth_layout"
              ? "Booth Layout agent"
              : "Standard agent"}
        </p>
      </motion.div>

      <Card className="mt-6">
        <CardContent className="space-y-5 p-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="provider">Model provider</Label>
              <Select
                id="provider"
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  setModel(MODELS[e.target.value][0]);
                }}
              >
                <option value="claude">Claude</option>
                <option value="openai">OpenAI</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="model">Model</Label>
              <Select
                id="model"
                value={model || models[0]}
                onChange={(e) => setModel(e.target.value)}
              >
                {models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div>
            <Label htmlFor="apikey">
              {provider === "openai" ? "OpenAI" : "Anthropic"} API key
            </Label>
            <Input
              id="apikey"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              autoComplete="off"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Stored with this agent. Leave blank to use the server&apos;s
              environment key.
            </p>
          </div>

          <div>
            <Label htmlFor="datasource">Data source</Label>
            <Select
              id="datasource"
              value={dataSourceId}
              onChange={(e) =>
                setDataSourceId(
                  e.target.value === "" ? "" : Number(e.target.value),
                )
              }
            >
              <option value="">None</option>
              {dataSources.map((ds) => (
                <option key={ds.id} value={ds.id}>
                  {ds.name}
                </option>
              ))}
            </Select>

            <div className="mt-3 flex flex-wrap items-center gap-2.5">
              <Input
                ref={fileInputRef}
                type="file"
                accept=".csv,.json,.xlsx,.xlsm"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="min-w-[12rem] flex-1 py-1.5"
              />
              <Button
                variant="secondary"
                onClick={upload}
                disabled={!file || busy === "upload"}
              >
                <Upload className="size-4" />
                {busy === "upload" ? "Uploading..." : "Ingest"}
              </Button>
              <Button
                onClick={build}
                disabled={dataSourceId === "" || busy === "build"}
              >
                <Hammer className="size-4" />
                {busy === "build" ? "Building..." : "Build ontology"}
              </Button>
            </div>

            <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm">
              <input
                type="checkbox"
                checked={allColumns}
                onChange={(e) => setAllColumns(e.target.checked)}
                className="mt-0.5 size-4 shrink-0 accent-accent"
              />
              <span>
                Treat every column as its own node
                <span className="block text-xs text-muted-foreground">
                  Star schema: each column becomes a class and each value a node
                  (e.g. Exhibitor Name, Balance Due), instead of high-cardinality
                  columns being kept as properties. Save, then Build to apply.
                </span>
              </span>
            </label>
          </div>

          {notice && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Database className="size-4 shrink-0 text-accent" />
              {notice}
            </p>
          )}

          {summary && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="metal grid grid-cols-2 gap-3 p-4 sm:grid-cols-4"
            >
              {(
                [
                  ["Classes", summary.classes],
                  ["Relations", summary.relations],
                  ["Nodes", summary.nodes],
                  ["Edges", summary.edges],
                ] as const
              ).map(([k, v]) => (
                <div key={k}>
                  <div className="text-2xl font-bold tabular-nums">{v}</div>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">
                    {k}
                  </div>
                </div>
              ))}
            </motion.div>
          )}

          <div>
            <Label htmlFor="systemprompt">System prompt</Label>
            <Textarea
              id="systemprompt"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={4}
              placeholder="Sets the agent's persona and behavior, e.g. “You are a concise booth-services concierge. Prefer tables over prose.”"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Controls how the agent behaves. The platform&apos;s data-grounding
              rules are always enforced on top of this.
            </p>
          </div>

          <div>
            <Label htmlFor="ontology">Ontology instructions</Label>
            <Textarea
              id="ontology"
              value={ontology}
              onChange={(e) => setOntology(e.target.value)}
              rows={3}
              placeholder="Guidance for how this agent should build and use the ontology layer."
            />
          </div>

          <div className="flex items-center gap-3">
            <Button onClick={save}>
              <Check className="size-4" />
              Save
            </Button>
            <Button variant="outline" onClick={remove} className="text-destructive">
              <Trash2 className="size-4" />
              Delete agent
            </Button>
            {saved && (
              <motion.span
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                className="inline-flex items-center gap-1 text-sm font-semibold text-success"
              >
                <Check className="size-4" />
                Saved
              </motion.span>
            )}
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
