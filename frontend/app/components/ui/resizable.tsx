"use client";

import { PanelResizeHandle } from "react-resizable-panels";
import { cn } from "@/lib/utils";

/** Themed drag handle for react-resizable-panels. `direction` is the parent
 *  PanelGroup's direction: a horizontal group needs a vertical grab bar. */
export function ResizeHandle({
  direction = "horizontal",
  className,
}: {
  direction?: "horizontal" | "vertical";
  className?: string;
}) {
  const horizontal = direction === "horizontal";
  return (
    <PanelResizeHandle
      className={cn(
        "group relative flex shrink-0 items-center justify-center",
        horizontal ? "w-2.5 cursor-col-resize" : "h-2.5 cursor-row-resize",
        className,
      )}
    >
      <span
        className={cn(
          "rounded-full bg-border transition-colors group-hover:bg-accent group-data-[resize-handle-state=drag]:bg-accent",
          horizontal ? "h-14 w-1" : "h-1 w-14",
        )}
      />
    </PanelResizeHandle>
  );
}
