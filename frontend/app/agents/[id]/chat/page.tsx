"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Panel, PanelGroup } from "react-resizable-panels";
import { Network, SendHorizonal, Sparkles } from "lucide-react";
import { api, Artifact, ChatMessage, Traversal } from "@/lib/api";
import OntologyPanel from "@/app/components/OntologyPanel";
import Canvas from "@/app/components/Canvas";
import { Button } from "@/app/components/ui/button";
import { Input } from "@/app/components/ui/input";
import { ResizeHandle } from "@/app/components/ui/resizable";
import { cn } from "@/lib/utils";

/** Track the lg breakpoint so the workspace splits horizontally on wide screens
 *  and stacks (still resizable) on narrow ones. */
function useWideScreen() {
  const [wide, setWide] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const update = () => setWide(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return wide;
}

export default function Chat() {
  const agentId = Number(useParams().id);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [traversal, setTraversal] = useState<Traversal | null>(null);
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [projectId, setProjectId] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const wide = useWideScreen();

  useEffect(() => {
    api
      .getAgent(agentId)
      .then((a) => setProjectId(a.show_project_id))
      .catch(() => {});
    api
      .getMessages(agentId)
      .then((m) => {
        setMessages(m);
        const lastArtifact = [...m]
          .reverse()
          .find((x) => x.metadata?.artifact);
        if (lastArtifact?.metadata.artifact)
          setArtifact(lastArtifact.metadata.artifact);
      })
      .catch(() => {});
  }, [agentId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(e: FormEvent) {
    e.preventDefault();
    const content = input.trim();
    if (!content || sending) return;
    setInput("");
    setError(null);
    setMessages((m) => [
      ...m,
      { role: "user", content, metadata: {}, created_at: "" },
    ]);
    setSending(true);
    try {
      const reply = await api.chat(agentId, content);
      setTraversal(reply.traversal);
      if (reply.artifact) setArtifact(reply.artifact);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: reply.content,
          metadata: { traversal: reply.traversal },
          created_at: "",
        },
      ]);
    } catch {
      setError(
        "The agent could not respond. Check the model provider's API key.",
      );
    } finally {
      setSending(false);
    }
  }

  const chatPane = (
    <section className="glass flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-muted-foreground">
            <span className="mb-3 grid size-12 place-items-center rounded-2xl bg-accent/15 text-accent">
              <Sparkles className="size-5" />
            </span>
            <p className="text-sm">Ask this agent a question to begin.</p>
          </div>
        )}
        {messages.map((m, i) => {
          const isUser = m.role === "user";
          const nodes = m.metadata?.traversal?.nodes ?? [];
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className={cn("flex", isUser ? "justify-end" : "justify-start")}
            >
              <div
                className={cn(
                  "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm",
                  isUser
                    ? "bg-[linear-gradient(180deg,#ff9678,#ff7a59_55%,#ef5f3d)] text-white shadow-[0_10px_24px_-14px_rgba(255,122,89,0.9)]"
                    : "bg-secondary text-foreground",
                )}
              >
                {m.content}
                {!isUser && nodes.length > 0 && (
                  <div className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-accent">
                    <Network className="size-3.5" />
                    Ontology traversal: {nodes.length} node
                    {nodes.length === 1 ? "" : "s"}
                  </div>
                )}
              </div>
            </motion.div>
          );
        })}
        <AnimatePresence>
          {sending && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-sm text-muted-foreground"
            >
              Thinking…
            </motion.p>
          )}
        </AnimatePresence>
        {error && <p className="text-sm font-medium text-destructive">{error}</p>}
        <div ref={endRef} />
      </div>

      <form onSubmit={send} className="flex shrink-0 gap-2 border-t border-border/70 p-3">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message the agent..."
          className="border-0 bg-secondary/60 shadow-none"
        />
        <Button type="submit" size="icon" disabled={sending}>
          <SendHorizonal className="size-4" />
        </Button>
      </form>
    </section>
  );

  const sidePane = (
    <PanelGroup direction="vertical" autoSaveId="inshow-chat-side" className="h-full">
      <Panel defaultSize={58} minSize={20} className="min-h-0">
        <OntologyPanel traversal={traversal} projectId={projectId} />
      </Panel>
      <ResizeHandle direction="vertical" />
      <Panel defaultSize={42} minSize={15} className="min-h-0">
        <div className="h-full overflow-auto">
          <Canvas artifact={artifact} />
        </div>
      </Panel>
    </PanelGroup>
  );

  return (
    <main className="h-[calc(100vh-3.5rem)] p-3 sm:p-4">
      <PanelGroup
        direction={wide ? "horizontal" : "vertical"}
        autoSaveId={wide ? "inshow-chat-h" : "inshow-chat-v"}
        className="h-full"
      >
        <Panel defaultSize={56} minSize={28} className="min-h-0">
          {chatPane}
        </Panel>
        <ResizeHandle direction={wide ? "horizontal" : "vertical"} />
        <Panel defaultSize={44} minSize={25} className="min-h-0">
          {sidePane}
        </Panel>
      </PanelGroup>
    </main>
  );
}
