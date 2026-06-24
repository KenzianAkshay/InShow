"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, Agent } from "@/lib/api";
import { cn } from "@/lib/utils";

// An agent is "live" once it has been configured with a model provider; until
// then it is "offline" (created but not ready to run).
function isLive(a: Agent): boolean {
  return Boolean(a.model_provider);
}

function Dot({ live = false }: { live?: boolean }) {
  return (
    <span
      className={cn(
        "inline-block size-2 rounded-full",
        live
          ? "bg-success shadow-[0_0_0_3px_color-mix(in_oklab,var(--success)_28%,transparent)]"
          : "bg-muted-foreground/50",
      )}
    />
  );
}

export default function AgentRibbon({
  projectId,
  currentAgentId,
}: {
  projectId: number | null;
  currentAgentId?: number;
}) {
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    if (projectId === null) return;
    api.listAgents(projectId).then(setAgents).catch(() => {});
  }, [projectId]);

  if (agents.length === 0) return null;

  const live = agents.filter(isLive).length;
  const offline = agents.length - live;

  return (
    <div className="glass mb-5 p-3.5">
      <div className="mb-2.5 flex items-center gap-4 text-xs text-muted-foreground">
        <strong className="font-semibold text-foreground">Agents</strong>
        <span className="inline-flex items-center gap-1.5">
          <Dot live /> {live} live
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Dot /> {offline} offline
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {agents.map((a) => {
          const current = a.id === currentAgentId;
          return (
            <Link
              key={a.id}
              href={`/agents/${a.id}`}
              title={
                isLive(a)
                  ? `${a.model_provider}/${a.model_name}`
                  : "Not configured"
              }
              className={cn(
                "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition-all hover:-translate-y-px",
                current
                  ? "border-transparent bg-accent text-accent-foreground shadow-[0_8px_20px_-12px_var(--accent)]"
                  : "border-border bg-[var(--glass-bg)] text-foreground backdrop-blur-md hover:border-ring/40",
              )}
            >
              <Dot live={isLive(a)} />
              {a.name}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
