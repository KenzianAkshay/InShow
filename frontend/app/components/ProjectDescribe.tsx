"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bot,
  Boxes,
  ChevronDown,
  Cpu,
  Database,
  FileJson,
  FileSpreadsheet,
  FileText,
  Layers,
  LayoutPanelTop,
  Network,
  Share2,
  Spline,
  Table2,
  X,
} from "lucide-react";
import { api, ProjectDescription } from "@/lib/api";
import { Skeleton } from "@/app/components/ui/skeleton";

type Props = { projectId: number; onClose: () => void };

function dataSourceIcon(type: string) {
  const t = type.toLowerCase();
  if (t.includes("json")) return FileJson;
  if (t.includes("csv") || t.includes("xls")) return FileSpreadsheet;
  return FileText;
}

function agentMeta(type: string): { Icon: typeof Bot; label: string } {
  if (type === "ontology_creation") return { Icon: Network, label: "Ontology Creation" };
  if (type === "booth_layout") return { Icon: LayoutPanelTop, label: "Booth Layout" };
  return { Icon: Bot, label: "Standard" };
}

type DsItem = {
  key: string;
  title: string;
  file: string | null; // set when this item is a tab within a workbook
  type: string;
  status: string;
  records: number | null;
};

/** Expand each data source into its tabs: a multi-tab workbook becomes one item
 *  per tab; a single-sheet file (CSV/JSON/one-tab Excel) stays a single item. */
function flattenDataSources(
  sources: ProjectDescription["data_sources"],
): DsItem[] {
  return sources.flatMap((ds): DsItem[] => {
    if (ds.sheets && ds.sheets.length > 1) {
      return ds.sheets.map((s) => ({
        key: `${ds.id}:${s.name}`,
        title: s.name,
        file: ds.name,
        type: ds.type,
        status: ds.status,
        records: s.records,
      }));
    }
    return [
      {
        key: String(ds.id),
        title: ds.name,
        file: null,
        type: ds.type,
        status: ds.status,
        records: ds.sheets?.[0]?.records ?? null,
      },
    ];
  });
}

/** A single horizontal layer band in the stack. */
function Layer({
  index,
  icon: Icon,
  title,
  subtitle,
  accent,
  children,
}: {
  index: number;
  icon: typeof Bot;
  title: string;
  subtitle: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08 }}
      className="glass relative overflow-hidden p-4 sm:p-5"
    >
      <div
        className="pointer-events-none absolute inset-y-0 left-0 w-1"
        style={{ background: accent }}
      />
      <div className="mb-3 flex items-center gap-3">
        <span
          className="grid size-10 shrink-0 place-items-center rounded-xl"
          style={{ background: `${accent}26`, color: accent }}
        >
          <Icon className="size-5" />
        </span>
        <div className="min-w-0">
          <h3 className="text-base font-semibold leading-tight">{title}</h3>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      {children}
    </motion.section>
  );
}

function Connector({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center py-1 text-muted-foreground">
      <span className="h-4 w-px bg-border" />
      <span className="flex items-center gap-1 text-[0.68rem] uppercase tracking-wide">
        <ChevronDown className="size-3" />
        {label}
      </span>
      <span className="h-4 w-px bg-border" />
    </div>
  );
}

function CountChip({
  icon: Icon,
  name,
  count,
  accent,
}: {
  icon: typeof Bot;
  name: string;
  count: number;
  accent: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-[var(--glass-bg)] py-1 pl-2 pr-1 text-xs font-medium backdrop-blur-md">
      <Icon className="size-3.5" style={{ color: accent }} />
      {name}
      <span className="rounded-full bg-secondary px-1.5 py-0.5 text-[0.68rem] font-semibold tabular-nums text-muted-foreground">
        {count}
      </span>
    </span>
  );
}

export default function ProjectDescribe({ projectId, onClose }: Props) {
  const [data, setData] = useState<ProjectDescription | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.describeProject(projectId).then(setData).catch(() => setError(true));
  }, [projectId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const ACCENT = { agents: "#ff7a59", ontology: "#a78bfa", data: "#0091ae" };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-background/70 p-4 backdrop-blur-sm sm:p-8"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.98 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          onClick={(e) => e.stopPropagation()}
          className="glass my-auto w-full max-w-5xl overflow-hidden"
        >
          {/* header */}
          <div className="metal flex items-center justify-between gap-3 rounded-none border-x-0 border-t-0 px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-xl bg-[linear-gradient(180deg,#ff9678,#ff7a59_55%,#ef5f3d)] text-white shadow-[0_8px_20px_-10px_rgba(255,122,89,0.9)]">
                <Layers className="size-5" />
              </span>
              <div>
                <h2 className="text-lg font-bold tracking-tight">Project Atlas</h2>
                <p className="text-xs text-muted-foreground">
                  {data ? data.project.name : "Reading project components…"}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              aria-label="Close"
              className="ring-focus grid size-9 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>

          <div className="max-h-[calc(90vh-5rem)] space-y-0 overflow-y-auto p-5">
            {error && (
              <p className="py-10 text-center text-sm text-destructive">
                Could not load this project&apos;s components.
              </p>
            )}

            {!data && !error && (
              <div className="space-y-4">
                <Skeleton className="h-28 w-full" />
                <Skeleton className="h-28 w-full" />
                <Skeleton className="h-28 w-full" />
              </div>
            )}

            {data && (
              <>
                {/* TOP — Agents */}
                <Layer
                  index={0}
                  icon={Bot}
                  title="Agents"
                  subtitle={`${data.agents.length} agent${data.agents.length === 1 ? "" : "s"} built on this project`}
                  accent={ACCENT.agents}
                >
                  {data.agents.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No agents yet.</p>
                  ) : (
                    <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                      {data.agents.map((a) => {
                        const { Icon, label } = agentMeta(a.type);
                        return (
                          <div
                            key={a.id}
                            className="flex items-center gap-3 rounded-[var(--radius-md)] border border-border bg-[var(--glass-bg)] p-3 backdrop-blur-md"
                          >
                            <span
                              className="grid size-9 shrink-0 place-items-center rounded-lg"
                              style={{ background: `${ACCENT.agents}1f`, color: ACCENT.agents }}
                            >
                              <Icon className="size-4" />
                            </span>
                            <div className="min-w-0">
                              <div className="truncate text-sm font-semibold">{a.name}</div>
                              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                <span>{label}</span>
                                {a.model_provider && (
                                  <span className="inline-flex items-center gap-1">
                                    <Cpu className="size-3" />
                                    {a.model_provider}/{a.model_name}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </Layer>

                <Connector label="operate over" />

                {/* MIDDLE — Ontology layer */}
                <Layer
                  index={1}
                  icon={Network}
                  title="Ontology layer"
                  subtitle={`${data.ontology.node_total} nodes · ${data.ontology.relation_total} relationships · ${data.ontology.classes.length} node types · ${data.ontology.relations.length} relationship types`}
                  accent={ACCENT.ontology}
                >
                  {data.ontology.node_total === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No ontology built yet. Ingest data and build the ontology from an
                      agent&apos;s setup page.
                    </p>
                  ) : (
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          <Boxes className="size-3.5" /> Node types
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {data.ontology.classes.map((c) => (
                            <CountChip
                              key={c.name}
                              icon={Boxes}
                              name={c.name}
                              count={c.count}
                              accent={ACCENT.ontology}
                            />
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          <Share2 className="size-3.5" /> Relationship types
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {data.ontology.relations.length === 0 ? (
                            <span className="text-xs text-muted-foreground">
                              No relationships generated.
                            </span>
                          ) : (
                            data.ontology.relations.map((r) => (
                              <CountChip
                                key={r.name}
                                icon={Spline}
                                name={r.name}
                                count={r.count}
                                accent={ACCENT.ontology}
                              />
                            ))
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </Layer>

                <Connector label="instantiated from" />

                {/* BOTTOM — Data sources (one component per tab for workbooks) */}
                {(() => {
                  const items = flattenDataSources(data.data_sources);
                  const files = data.data_sources.length;
                  const subtitle =
                    `${files} ingested file${files === 1 ? "" : "s"}` +
                    (items.length > files ? ` · ${items.length} tabs` : "");
                  return (
                    <Layer
                      index={2}
                      icon={Database}
                      title="Data sources"
                      subtitle={subtitle}
                      accent={ACCENT.data}
                    >
                      {items.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                          No data ingested yet.
                        </p>
                      ) : (
                        <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                          {items.map((item) => {
                            const Icon = item.file
                              ? Table2
                              : dataSourceIcon(item.type);
                            return (
                              <div
                                key={item.key}
                                className="flex items-center gap-3 rounded-[var(--radius-md)] border border-border bg-[var(--glass-bg)] p-3 backdrop-blur-md"
                              >
                                <span
                                  className="grid size-9 shrink-0 place-items-center rounded-lg"
                                  style={{
                                    background: `${ACCENT.data}1f`,
                                    color: ACCENT.data,
                                  }}
                                >
                                  <Icon className="size-4" />
                                </span>
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-semibold">
                                    {item.title}
                                  </div>
                                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                    {item.file ? (
                                      <span className="truncate" title={item.file}>
                                        {item.file}
                                      </span>
                                    ) : (
                                      <span className="uppercase">{item.type}</span>
                                    )}
                                    {item.records != null && (
                                      <span className="shrink-0 rounded-full bg-secondary px-1.5 py-0.5 text-[0.68rem] font-medium tabular-nums">
                                        {item.records} rec
                                      </span>
                                    )}
                                    <span className="shrink-0 rounded-full bg-secondary px-1.5 py-0.5 text-[0.68rem] font-medium">
                                      {item.status}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </Layer>
                  );
                })()}
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
