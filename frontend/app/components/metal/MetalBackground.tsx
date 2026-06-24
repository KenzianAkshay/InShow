"use client";

/**
 * Fixed, GPU-cheap app backdrop: a faint blueprint grid plus two slowly
 * drifting brand-coloured glows. Sits behind all content and adapts to theme
 * via CSS tokens (`--app-glow-1/2`, `--grid-line`).
 */
export default function MetalBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      {/* Blueprint grid */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(var(--grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--grid-line) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage:
            "radial-gradient(circle at 50% 30%, black, transparent 80%)",
          WebkitMaskImage:
            "radial-gradient(circle at 50% 30%, black, transparent 80%)",
        }}
      />
      {/* Drifting glows */}
      <div
        className="absolute -left-[10%] -top-[15%] h-[55vw] w-[55vw] rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(circle, var(--app-glow-1), transparent 70%)",
          animation: "glow-drift 22s ease-in-out infinite",
        }}
      />
      <div
        className="absolute -right-[12%] top-[25%] h-[50vw] w-[50vw] rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(circle, var(--app-glow-2), transparent 70%)",
          animation: "glow-drift 28s ease-in-out infinite reverse",
        }}
      />
    </div>
  );
}
