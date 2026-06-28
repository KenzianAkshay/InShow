"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ChevronRight, LogOut } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/app/components/ui/button";
import { LogoMark } from "@/app/components/Logo";
import ThemeToggle from "@/app/components/metal/ThemeToggle";

type Crumb = { label: string; href: string };

function BrandMark() {
  return (
    <Link href="/" className="group flex items-center gap-2">
      <span className="relative grid size-8 place-items-center rounded-[10px] bg-[linear-gradient(180deg,#ff9678,#ff7a59_55%,#ef5f3d)] text-white shadow-[0_6px_16px_-8px_rgba(255,122,89,0.9)]">
        <LogoMark className="size-[18px]" />
      </span>
      <span className="text-[1.05rem] font-bold tracking-tight text-foreground">
        ShowSphere
      </span>
    </Link>
  );
}

export default function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const [crumbs, setCrumbs] = useState<Crumb[]>([]);
  const [agentTab, setAgentTab] = useState<{ id: number; chat: boolean } | null>(
    null,
  );

  useEffect(() => {
    const segs = pathname.split("/").filter(Boolean);
    setAgentTab(null);

    if (segs[0] === "projects" && segs[1]) {
      const pid = Number(segs[1]);
      api
        .getProject(pid)
        .then((p) => setCrumbs([{ label: p.name, href: `/projects/${pid}` }]))
        .catch(() => setCrumbs([]));
      return;
    }

    if (segs[0] === "agents" && segs[1]) {
      const aid = Number(segs[1]);
      const isChat = segs[2] === "chat";
      setAgentTab({ id: aid, chat: isChat });
      api
        .getAgent(aid)
        .then(async (a) => {
          const next: Crumb[] = [];
          if (a.show_project_id !== null) {
            try {
              const p = await api.getProject(a.show_project_id);
              next.push({ label: p.name, href: `/projects/${p.id}` });
            } catch {
              // project unavailable; skip its crumb
            }
          }
          next.push({ label: a.name, href: `/agents/${aid}` });
          setCrumbs(next);
        })
        .catch(() => setCrumbs([]));
      return;
    }

    setCrumbs([]);
  }, [pathname]);

  async function logout() {
    await api.logout();
    router.push("/login");
    router.refresh();
  }

  if (pathname === "/login") {
    return (
      <header className="sticky top-0 z-40 flex h-14 items-center px-5">
        <BrandMark />
      </header>
    );
  }

  return (
    <header className="glass sticky top-0 z-40 flex h-14 items-center justify-between gap-3 rounded-none border-x-0 border-t-0 px-4 sm:px-6">
      <nav className="flex min-w-0 items-center gap-2 text-sm">
        <BrandMark />
        <ChevronRight className="size-4 shrink-0 text-muted-foreground/60" />
        <Link
          href="/"
          className="shrink-0 text-muted-foreground transition-colors hover:text-foreground"
        >
          Show Projects
        </Link>
        {crumbs.map((c) => (
          <span key={c.href} className="flex min-w-0 items-center gap-2">
            <ChevronRight className="size-4 shrink-0 text-muted-foreground/60" />
            <Link
              href={c.href}
              className="truncate text-muted-foreground transition-colors hover:text-foreground"
            >
              {c.label}
            </Link>
          </span>
        ))}
      </nav>

      <div className="flex items-center gap-2">
        {agentTab && (
          <div className="glass flex rounded-full p-1">
            <Link
              href={`/agents/${agentTab.id}`}
              className={cn(
                "rounded-full px-3.5 py-1 text-xs font-semibold transition-colors",
                agentTab.chat
                  ? "text-muted-foreground hover:text-foreground"
                  : "bg-[linear-gradient(180deg,#ff9678,#ff7a59_55%,#ef5f3d)] text-white shadow-[0_6px_16px_-10px_rgba(255,122,89,0.9)]",
              )}
            >
              Setup
            </Link>
            <Link
              href={`/agents/${agentTab.id}/chat`}
              className={cn(
                "rounded-full px-3.5 py-1 text-xs font-semibold transition-colors",
                agentTab.chat
                  ? "bg-[linear-gradient(180deg,#ff9678,#ff7a59_55%,#ef5f3d)] text-white shadow-[0_6px_16px_-10px_rgba(255,122,89,0.9)]"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              Chat
            </Link>
          </div>
        )}
        <ThemeToggle />
        <Button variant="outline" size="sm" onClick={logout} className="gap-1.5">
          <LogOut className="size-3.5" />
          <span className="hidden sm:inline">Log out</span>
        </Button>
      </div>
    </header>
  );
}
