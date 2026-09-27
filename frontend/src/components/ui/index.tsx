// shadcn/ui-style primitives (copy-in components, Tailwind + cva), kept in one file for the prototype.
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600/60",
  {
    variants: {
      variant: {
        default: "bg-teal-700 text-white hover:bg-teal-800",
        outline: "border hairline bg-[var(--panel)] hover:bg-[var(--panel-2)]",
        ghost: "hover:bg-[var(--panel-2)]",
        danger: "bg-red-600 text-white hover:bg-red-700",
        success: "bg-green-600 text-white hover:bg-green-700",
        amber: "bg-amber-500 text-white hover:bg-amber-600",
        blue: "bg-blue-600 text-white hover:bg-blue-700",
      },
      size: { sm: "h-8 px-3 text-xs", md: "h-9 px-4", lg: "h-11 px-5 text-base", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "default", size: "md" },
  }
);

export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>>(
  ({ className, variant, size, ...props }, ref) => <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
);

export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("panel", className)} {...p} />;
}
export function CardHeader({ title, subtitle, right, className }: { title: React.ReactNode; subtitle?: React.ReactNode; right?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-3 px-4 pt-3 pb-2", className)}>
      <div>
        <div className="text-sm font-semibold">{title}</div>
        {subtitle && <div className="text-xs muted mt-0.5">{subtitle}</div>}
      </div>
      {right}
    </div>
  );
}

export function Badge({ className, color, children }: { className?: string; color?: string; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium leading-none", className)}
      style={color ? { background: color + "1f", color, border: `1px solid ${color}40` } : undefined}>
      {children}
    </span>
  );
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn("h-9 w-full rounded-lg border hairline bg-[var(--panel)] px-3 text-sm outline-none focus:ring-2 focus:ring-teal-600/40", className)} {...p} />
));

export function Select({ className, children, ...p }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn("h-9 rounded-lg border hairline bg-[var(--panel)] px-2 text-sm outline-none focus:ring-2 focus:ring-teal-600/40", className)} {...p}>
      {children}
    </select>
  );
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded border hairline bg-[var(--panel-2)] px-1.5 py-0.5 font-mono text-[10px]">{children}</kbd>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="py-10 text-center text-sm muted">{children}</div>;
}

export function Toast({ msg, onClose, tone = "teal" }: { msg: string | null; onClose: () => void; tone?: "teal" | "red" | "green" }) {
  React.useEffect(() => {
    if (!msg) return;
    const t = setTimeout(onClose, 4200);
    return () => clearTimeout(t);
  }, [msg]);
  if (!msg) return null;
  const bg = tone === "red" ? "bg-red-600" : tone === "green" ? "bg-green-600" : "bg-teal-700";
  return <div className={cn("fixed bottom-6 left-1/2 z-[1000] -translate-x-1/2 rounded-xl px-4 py-3 text-sm text-white shadow-xl", bg)}>{msg}</div>;
}
