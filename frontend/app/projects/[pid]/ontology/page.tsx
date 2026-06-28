"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Download } from "lucide-react";
import { api, ShowProject } from "@/lib/api";
import OntologyPanel from "@/app/components/OntologyPanel";

export default function OntologyPage() {
  const projectId = Number(useParams().pid);
  const [project, setProject] = useState<ShowProject | null>(null);

  useEffect(() => {
    api.getProject(projectId).then(setProject).catch(() => {});
  }, [projectId]);

  const exportHref = (scope: "full" | "schema") =>
    `/api/ontology/export?project_id=${projectId}&scope=${scope}`;

  return (
    <main className="flex h-[calc(100vh-3.5rem)] flex-col p-3 sm:p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Link
            href={`/projects/${projectId}`}
            className="ring-focus inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            aria-label="Back to project"
          >
            <ArrowLeft className="size-4" />
          </Link>
          <h1 className="truncate text-xl font-bold tracking-tight">
            {project?.name ?? "Project"} · Ontology
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={exportHref("schema")}
            download
            className="ring-focus inline-flex items-center gap-1.5 rounded-lg border border-border bg-[var(--glass-bg)] px-3 py-2 text-sm font-medium text-muted-foreground backdrop-blur-md transition-colors hover:text-foreground"
          >
            <Download className="size-4" />
            Schema (JSON-LD)
          </a>
          <a
            href={exportHref("full")}
            download
            className="ring-focus inline-flex items-center gap-1.5 rounded-lg bg-[linear-gradient(180deg,#ff9678,#ff7a59_55%,#ef5f3d)] px-3 py-2 text-sm font-semibold text-white shadow-[0_10px_24px_-14px_rgba(255,122,89,0.9)]"
          >
            <Download className="size-4" />
            Export JSON-LD
          </a>
        </div>
      </div>

      <div className="min-h-0 flex-1">
        <OntologyPanel traversal={null} projectId={projectId} />
      </div>
    </main>
  );
}
