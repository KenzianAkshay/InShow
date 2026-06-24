import * as React from "react";
import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "ring-focus flex min-h-20 w-full rounded-[var(--radius-md)] border border-input bg-[var(--glass-bg)] px-3.5 py-2.5 text-sm text-foreground shadow-sm backdrop-blur-md transition-colors",
      "placeholder:text-muted-foreground/70 hover:border-ring/40 disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export { Textarea };
