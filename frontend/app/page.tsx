"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, FolderPlus, Layers, Plus } from "lucide-react";
import { api, ShowProject } from "@/lib/api";
import { Button } from "@/app/components/ui/button";
import { Input } from "@/app/components/ui/input";
import { Badge } from "@/app/components/ui/badge";

export default function Dashboard() {
  const [username, setUsername] = useState<string | null>(null);
  const [projects, setProjects] = useState<ShowProject[]>([]);
  const [name, setName] = useState("");
  const router = useRouter();

  useEffect(() => {
    api
      .me()
      .then((d) => setUsername(d.username))
      .catch(() => router.push("/login"));
    api.listProjects().then(setProjects).catch(() => {});
  }, [router]);

  async function createProject(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const project = await api.createProject(name.trim());
    setName("");
    router.push(`/projects/${project.id}`);
  }

  if (!username) return null;

  return (
    <main className="mx-auto max-w-4xl px-5 py-10">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">Show Projects</h1>
          <Badge variant="muted">Signed in as {username}</Badge>
        </div>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">
          Each show project holds its own agents and an evolving ontology shared
          across them.
        </p>

        <form onSubmit={createProject} className="glass mt-7 flex gap-3 p-3">
          <div className="relative flex-1">
            <FolderPlus className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="New show project name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="border-0 bg-transparent pl-10 shadow-none"
            />
          </div>
          <Button type="submit">
            <Plus className="size-4" />
            Create
          </Button>
        </form>
      </motion.div>

      {projects.length === 0 ? (
        <p className="mt-8 text-sm text-muted-foreground">
          No show projects yet. Create one to get started.
        </p>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {projects.map((p, i) => (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: Math.min(i * 0.04, 0.3) }}
            >
              <Link
                href={`/projects/${p.id}`}
                className="glass sheen group flex h-full items-center justify-between gap-4 p-5 transition-transform hover:-translate-y-0.5"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="grid size-9 place-items-center rounded-xl bg-accent/15 text-accent">
                      <Layers className="size-4" />
                    </span>
                    <span className="truncate text-base font-semibold">
                      {p.name}
                    </span>
                  </div>
                  <div className="mt-2 text-sm text-muted-foreground">
                    {p.agent_count ?? 0} agent{p.agent_count === 1 ? "" : "s"}
                    {p.description ? ` · ${p.description}` : ""}
                  </div>
                </div>
                <ArrowRight className="size-5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-accent" />
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </main>
  );
}
