"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Bot, Layers, Plus, Trash2, TriangleAlert } from "lucide-react";
import { api, Agent, ShowProject } from "@/lib/api";
import AgentRibbon from "@/app/components/AgentRibbon";
import ProjectDescribe from "@/app/components/ProjectDescribe";
import { Button } from "@/app/components/ui/button";
import { Input } from "@/app/components/ui/input";
import { Select } from "@/app/components/ui/select";
import { Badge } from "@/app/components/ui/badge";

export default function ProjectDetail() {
  const projectId = Number(useParams().pid);
  const router = useRouter();
  const [project, setProject] = useState<ShowProject | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("standard");
  const [describing, setDescribing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    api.getProject(projectId).then(setProject).catch(() => router.push("/"));
    api.listAgents(projectId).then(setAgents).catch(() => {});
  }, [projectId, router]);

  async function createAgent(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const agent = await api.createAgent(name.trim(), type, projectId);
    setName("");
    router.push(`/agents/${agent.id}`);
  }

  async function removeProject() {
    setDeleting(true);
    try {
      await api.deleteProject(projectId);
      router.push("/");
    } catch {
      setDeleting(false);
    }
  }

  if (!project) return null;

  return (
    <main className="mx-auto max-w-4xl px-5 py-10">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-3xl font-bold tracking-tight">{project.name}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={() => setDescribing(true)}>
              <Layers className="size-4" />
              Describe Project
            </Button>
            <Button
              variant="outline"
              onClick={() => setConfirmDelete(true)}
              className="text-destructive"
            >
              <Trash2 className="size-4" />
              Delete project
            </Button>
          </div>
        </div>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">
          Agents in this show share one evolving ontology. Build it from any
          agent&apos;s setup page; every data set you add extends it.
        </p>
      </motion.div>

      {describing && (
        <ProjectDescribe
          projectId={projectId}
          onClose={() => setDescribing(false)}
        />
      )}

      <AnimatePresence>
        {confirmDelete && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm"
            onClick={() => !deleting && setConfirmDelete(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              onClick={(e) => e.stopPropagation()}
              className="glass w-full max-w-md p-6"
            >
              <div className="flex items-center gap-3">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-destructive/15 text-destructive">
                  <TriangleAlert className="size-5" />
                </span>
                <div>
                  <h2 className="text-lg font-bold tracking-tight">
                    Delete this project?
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    &ldquo;{project.name}&rdquo;
                  </p>
                </div>
              </div>
              <p className="mt-4 text-sm text-muted-foreground">
                This permanently removes the project and all of its agents. This
                cannot be undone.
              </p>
              <div className="mt-6 flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => setConfirmDelete(false)}
                  disabled={deleting}
                >
                  Cancel
                </Button>
                <Button
                  onClick={removeProject}
                  disabled={deleting}
                  className="bg-destructive text-white hover:bg-destructive/90"
                >
                  <Trash2 className="size-4" />
                  {deleting ? "Deleting…" : "Delete project"}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-6">
        <AgentRibbon projectId={projectId} />
      </div>

      <h2 className="mb-3 text-xl font-semibold tracking-tight">Agents</h2>

      <form onSubmit={createAgent} className="glass flex flex-wrap gap-3 p-3">
        <Input
          placeholder="New agent name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="min-w-[12rem] flex-1 border-0 bg-transparent shadow-none"
        />
        <Select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="w-48"
        >
          <option value="standard">Standard</option>
          <option value="ontology_creation">Ontology Creation</option>
          <option value="booth_layout">Booth Layout</option>
        </Select>
        <Button type="submit">
          <Plus className="size-4" />
          Create
        </Button>
      </form>

      {agents.length === 0 ? (
        <p className="mt-6 text-sm text-muted-foreground">
          No agents yet. Create one to get started.
        </p>
      ) : (
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {agents.map((a, i) => (
            <motion.div
              key={a.id}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: Math.min(i * 0.04, 0.3) }}
            >
              <Link
                href={`/agents/${a.id}`}
                className="glass sheen group flex h-full items-center justify-between gap-4 p-5 transition-transform hover:-translate-y-0.5"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="grid size-9 place-items-center rounded-xl bg-primary/15 text-primary">
                      <Bot className="size-4" />
                    </span>
                    <span className="truncate text-base font-semibold">
                      {a.name}
                    </span>
                    {a.model_provider ? (
                      <Badge variant="success">live</Badge>
                    ) : (
                      <Badge variant="muted">offline</Badge>
                    )}
                  </div>
                  <div className="mt-2 text-sm text-muted-foreground">
                    {a.type === "ontology_creation"
                      ? "Ontology Creation"
                      : a.type === "booth_layout"
                        ? "Booth Layout"
                        : "Standard"}
                    {a.model_provider
                      ? ` · ${a.model_provider}/${a.model_name}`
                      : ""}
                  </div>
                </div>
                <ArrowRight className="size-5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </main>
  );
}
