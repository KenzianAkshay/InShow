import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "ring-focus inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-md)] text-sm font-semibold transition-all duration-200 disabled:pointer-events-none disabled:opacity-55 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "sheen border border-[color-mix(in_oklab,var(--primary)_60%,#000)] bg-[linear-gradient(180deg,#ff9678,#ff7a59_55%,#ef5f3d)] text-primary-foreground shadow-[0_10px_26px_-12px_rgba(255,122,89,0.85)] hover:brightness-[1.06] active:scale-[0.98]",
        secondary:
          "glass sheen text-foreground hover:-translate-y-px active:scale-[0.98]",
        outline:
          "border border-border bg-transparent text-foreground hover:bg-secondary active:scale-[0.98]",
        ghost: "text-foreground/80 hover:bg-secondary hover:text-foreground",
        accent:
          "bg-accent text-accent-foreground shadow-[0_10px_26px_-14px_var(--accent)] hover:brightness-110 active:scale-[0.98]",
        destructive:
          "border border-[color-mix(in_oklab,var(--destructive)_55%,#000)] bg-destructive text-destructive-foreground hover:brightness-110 active:scale-[0.98]",
      },
      size: {
        default: "h-10 px-5",
        sm: "h-8 px-3 text-xs",
        lg: "h-12 px-7 text-base",
        icon: "size-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";

export { Button };
