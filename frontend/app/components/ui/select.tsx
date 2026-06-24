import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Styled native <select>. Native keeps it dependency-light and fully
 * keyboard/screen-reader accessible; we just skin the control and overlay a
 * chevron. The option list uses the browser's popup (themed by the OS).
 */
const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <div className="relative">
    <select
      ref={ref}
      className={cn(
        "ring-focus h-10 w-full appearance-none rounded-[var(--radius-md)] border border-input bg-[var(--glass-bg)] px-3.5 pr-10 text-sm text-foreground shadow-sm backdrop-blur-md transition-colors hover:border-ring/40 disabled:cursor-not-allowed disabled:opacity-50",
        "[&>option]:bg-popover [&>option]:text-popover-foreground",
        className,
      )}
      {...props}
    >
      {children}
    </select>
    <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
  </div>
));
Select.displayName = "Select";

export { Select };
