import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, type, ...props }, ref) => (
  <input
    ref={ref}
    type={type}
    className={cn(
      "ring-focus flex h-10 w-full rounded-[var(--radius-md)] border border-input bg-[var(--glass-bg)] px-3.5 py-2 text-sm text-foreground shadow-sm backdrop-blur-md transition-colors",
      "placeholder:text-muted-foreground/70 hover:border-ring/40",
      "file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-secondary-foreground",
      "disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";

export { Input };
