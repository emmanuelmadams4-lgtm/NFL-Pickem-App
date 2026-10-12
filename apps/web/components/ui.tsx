"use client";

import { useId, useLayoutEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { ApiError } from "@nflpi/shared";
import { Check, X } from "@/components/icons";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof TypeError) return "Could not reach the API. Check that the server is running.";
  if (e instanceof Error) return e.message;
  return "Something went wrong.";
}

/* ---------- surfaces ---------- */

export function Card({ className, children, ...rest }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx("rounded-card border border-border bg-surface", className)} {...rest}>
      {children}
    </div>
  );
}

/**
 * The one elevated surface on a screen (design.md § 7): an `elevated` shell with a hairline ring around a `surface` core.
 * Used for the Model pick panel on Matchup and the sign-in card. Nowhere else.
 */
export function Bezel({
  className,
  coreClassName,
  children,
  ...rest
}: { className?: string; coreClassName?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx("enter rounded-bezel border border-border bg-elevated/60 p-1.5", className)} {...rest}>
      <div className={cx("rounded-card bg-surface shadow-[var(--shadow-inset-highlight),var(--shadow-float)]", coreClassName)}>{children}</div>
    </div>
  );
}

/** Unboxed section (design.md § 8): heading, optional note, hairline, content. */
export function Section({
  id,
  title,
  note,
  action,
  children,
  className,
}: {
  id?: string;
  title: string;
  note?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const headingId = useId();
  return (
    <section id={id} aria-labelledby={headingId} className={cx("scroll-mt-32", className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b border-border pb-3">
        <div className="min-w-0">
          <h2 id={headingId} className="text-heading text-text">
            {title}
          </h2>
          {note && <p className="mt-0.5 text-label text-subtle">{note}</p>}
        </div>
        {action}
      </div>
      <div className="pt-4">{children}</div>
    </section>
  );
}

/* ---------- chips ---------- */

export type ChipTone = "neutral" | "good" | "warn" | "warn-soft" | "bad" | "accent";

const chipTone: Record<ChipTone, string> = {
  neutral: "border-border bg-elevated text-text-2",
  good: "border-good/35 bg-good/12 text-good",
  warn: "border-warn/40 bg-warn/14 text-warn",
  "warn-soft": "border-warn/35 bg-transparent text-warn",
  bad: "border-bad/40 bg-bad/14 text-bad",
  accent: "border-accent/50 bg-transparent text-accent",
};

export function Chip({ tone = "neutral", children, className }: { tone?: ChipTone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-chip border px-1.5 py-px text-micro whitespace-nowrap",
        chipTone[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/**
 * Hover/focus tooltip. The trigger is keyboard focusable (and tap-focusable on phones) so reasons are not hover-only.
 * Closed tooltips are display:none so they never add scrollable width; open ones are nudged back inside the viewport.
 */
export function Tip({ content, children, className, align = "left" }: { content: ReactNode; children: ReactNode; className?: string; align?: "left" | "right" }) {
  const id = useId();
  const [hover, setHover] = useState(false);
  const [focus, setFocus] = useState(false);
  const [shift, setShift] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const open = hover || focus;

  useLayoutEffect(() => {
    if (!open) {
      setShift(0);
      return;
    }
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const vw = document.documentElement.clientWidth;
    let dx = 0;
    if (r.right > vw - 8) dx = vw - 8 - r.right;
    if (r.left + dx < 8) dx = 8 - r.left;
    setShift(dx);
  }, [open]);

  return (
    <span
      className={cx("relative z-10 inline-flex", open && "z-40", className)}
      onPointerEnter={(e) => e.pointerType === "mouse" && setHover(true)}
      onPointerLeave={(e) => e.pointerType === "mouse" && setHover(false)}
      onFocus={() => setFocus(true)}
      onBlur={() => setFocus(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          setHover(false);
          setFocus(false);
        }
      }}
    >
      <span tabIndex={0} aria-describedby={id} className="inline-flex rounded-chip">
        {children}
      </span>
      <span
        ref={ref}
        role="tooltip"
        id={id}
        hidden={!open}
        style={shift ? { transform: `translateX(${shift}px)` } : undefined}
        className={cx(
          "pointer-events-none absolute top-full z-40 mt-1.5 w-max max-w-[min(18rem,calc(100vw-1rem))] rounded-ctl border border-border bg-elevated p-3 text-left text-xs font-normal whitespace-normal text-text shadow-[var(--shadow-pop)]",
          align === "left" ? "left-0" : "right-0",
        )}
      >
        {content}
      </span>
    </span>
  );
}

/* ---------- buttons & form controls ---------- */

type Variant = "primary" | "secondary" | "ghost" | "danger";
const variantClass: Record<Variant, string> = {
  primary: "bg-accent-solid text-white border-transparent hover:brightness-110",
  secondary: "bg-elevated text-text border-border hover:border-border-strong",
  ghost: "bg-transparent text-text-2 border-transparent hover:bg-elevated hover:text-text",
  danger: "bg-transparent text-bad border-bad/40 hover:bg-bad/10",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-ctl border font-medium whitespace-nowrap transition-[transform,background-color,border-color,filter,opacity] duration-(--duration-press)",
        "active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50 disabled:active:translate-y-0",
        size === "sm" ? "h-9 px-3 text-xs lg:h-8" : "h-10 px-4 text-sm lg:h-9",
        variantClass[variant],
        className,
      )}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cx("spin inline-block size-3.5 rounded-full border-2 border-current border-t-transparent opacity-80", className)}
    />
  );
}

export function SelectField({
  label,
  className,
  labelClassName,
  children,
  hideLabel,
  grow,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; hideLabel?: boolean; labelClassName?: string; grow?: boolean }) {
  const id = useId();
  return (
    <span className={className ?? "inline-flex"}>
      <label htmlFor={id} className={cx("inline-flex items-center gap-2 text-xs text-text-2", grow && "w-full")}>
        <span className={hideLabel ? "sr-only" : labelClassName}>{label}</span>
        <select
          id={id}
          {...rest}
          className={cx("h-10 rounded-ctl border border-border-strong bg-elevated px-2 text-base text-text hover:border-text-2 lg:h-8 lg:text-sm", grow && "min-w-0 flex-1")}
        >
          {children}
        </select>
      </label>
    </span>
  );
}

export function Segmented<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string; disabled?: boolean }[];
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-ctl border border-border bg-elevated p-0.5">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={o.disabled}
            onClick={() => onChange(o.value)}
            className={cx(
              "h-9 rounded-[6px] px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45 lg:h-7 lg:text-xs",
              active ? "bg-surface text-text shadow-[0_0_0_1px_var(--border)]" : "text-text-2 hover:text-text",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/* ---------- states ---------- */

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("skeleton", className)} />;
}

export function ErrorState({ error, onRetry, title = "Could not load this" }: { error: unknown; onRetry?: () => void; title?: string }) {
  return (
    <div role="alert" className="rounded-card border border-bad/40 bg-bad/8 p-5">
      <p className="text-sm font-semibold text-bad">{title}</p>
      <p className="mt-1 text-sm text-text-2">{errorMessage(error)}</p>
      {onRetry && (
        <Button className="mt-3" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-card border border-dashed border-border px-6 py-10 text-center">
      <p className="text-sm font-medium text-text">{title}</p>
      {hint && <p className="mx-auto mt-1 max-w-md text-sm text-text-2">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Notice({ tone = "warn", title, children, className }: { tone?: "warn" | "bad" | "info" | "good"; title?: string; children?: ReactNode; className?: string }) {
  const t = {
    warn: "border-warn/40 bg-warn/10",
    bad: "border-bad/40 bg-bad/10",
    good: "border-good/40 bg-good/10",
    info: "border-border bg-elevated",
  }[tone];
  const h = { warn: "text-warn", bad: "text-bad", good: "text-good", info: "text-text" }[tone];
  return (
    <div role={tone === "bad" ? "alert" : "note"} className={cx("rounded-ctl border px-4 py-3 text-sm", t, className)}>
      {title && <p className={cx("font-semibold", h)}>{title}</p>}
      {children && <div className={cx("text-text-2", title && "mt-0.5")}>{children}</div>}
    </div>
  );
}

/* ---------- small pieces ---------- */

export function Stat({ label, value, sub, className }: { label: string; value: ReactNode; sub?: ReactNode; className?: string }) {
  return (
    <div className={cx("min-w-0", className)}>
      <p className="text-xs text-subtle">{label}</p>
      <p className="num-display mt-0.5 text-2xl leading-8 font-semibold text-text">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-text-2">{sub}</p>}
    </div>
  );
}

/** Correct / incorrect mark with screen-reader text. */
export function Mark({ correct, who }: { correct: boolean | null | undefined; who: string }) {
  if (correct === null || correct === undefined) return null;
  return (
    <span className={cx("inline-flex items-center gap-1 text-xs", correct ? "text-good" : "text-bad")}>
      <span className="text-text-2">{who}</span>
      {correct ? <Check size={14} /> : <X size={14} />}
      <span className="sr-only">{correct ? "correct" : "incorrect"}</span>
    </span>
  );
}

export function DataNote({ children }: { children: ReactNode }) {
  return <p className="text-xs text-subtle">{children}</p>;
}
