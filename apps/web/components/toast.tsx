"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

type Tone = "info" | "good" | "warn" | "bad";
interface ToastItem {
  id: number;
  message: string;
  tone: Tone;
  action?: { label: string; onClick: () => void };
}

const ToastContext = createContext<{ toast: (message: string, tone?: Tone, action?: ToastItem["action"]) => void } | null>(null);

const toneClass: Record<Tone, string> = {
  info: "border-border",
  good: "border-good/50",
  warn: "border-warn/50",
  bad: "border-bad/50",
};
const toneLabel: Record<Tone, string> = { info: "Notice", good: "Done", warn: "Heads up", bad: "Error" };
const toneText: Record<Tone, string> = { info: "text-text-2", good: "text-good", warn: "text-warn", bad: "text-bad" };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);

  const toast = useCallback((message: string, tone: Tone = "info", action?: ToastItem["action"]) => {
    const id = next.current++;
    setItems((cur) => [...cur.filter((item) => item.action), ...cur.filter((item) => !item.action).slice(-2), { id, message, tone, action }]);
    if (!action) window.setTimeout(() => setItems((cur) => cur.filter((t) => t.id !== id)), 5000);
  }, []);

  const value = useMemo(() => ({ toast }), [toast]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed right-4 bottom-[calc(84px+env(safe-area-inset-bottom))] left-4 z-50 ml-auto lg:bottom-4 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2"
      >
        {items.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`enter pointer-events-auto rounded-ctl border bg-elevated px-3 py-2 text-sm shadow-[var(--shadow-pop)] ${toneClass[t.tone]}`}
          >
            <span className={`mr-2 text-xs font-semibold ${toneText[t.tone]}`}>{toneLabel[t.tone]}</span>
            <span className="text-text">{t.message}</span>
            {t.action && (
              <button
                type="button"
                className="ml-3 min-h-11 rounded-ctl px-3 font-semibold text-accent"
                onClick={() => {
                  setItems((cur) => cur.filter((item) => item.id !== t.id));
                  t.action?.onClick();
                }}
              >
                {t.action.label}
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
