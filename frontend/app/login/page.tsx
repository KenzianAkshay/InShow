"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Hexagon, LogIn } from "lucide-react";
import { Button } from "@/app/components/ui/button";
import { Input } from "@/app/components/ui/input";
import { Label } from "@/app/components/ui/label";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (res.ok) {
      router.push("/");
      router.refresh();
    } else {
      setError("Invalid username or password");
    }
  }

  return (
    <main className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4 py-16">
      <motion.form
        onSubmit={submit}
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="glass sheen w-full max-w-sm p-8"
      >
        <span className="mb-5 grid size-12 place-items-center rounded-2xl bg-[linear-gradient(180deg,#ff9678,#ff7a59_55%,#ef5f3d)] shadow-[0_12px_30px_-12px_rgba(255,122,89,0.9)]">
          <Hexagon className="size-6 text-white" strokeWidth={2.4} />
        </span>

        <h1 className="mb-1 text-2xl font-bold tracking-tight">Sign in</h1>
        <p className="mb-7 text-sm text-muted-foreground">
          InShow Exhibitor Services Agent Platform
        </p>

        <div className="mb-4">
          <Label htmlFor="username">Username</Label>
          <Input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />
        </div>

        <div className="mb-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>

        {error && (
          <p className="mb-3 text-sm font-medium text-destructive">{error}</p>
        )}

        <Button type="submit" className="mt-4 w-full">
          <LogIn className="size-4" />
          Sign in
        </Button>
      </motion.form>
    </main>
  );
}
