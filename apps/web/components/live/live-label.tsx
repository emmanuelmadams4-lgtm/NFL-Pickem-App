import type { CardLiveState } from "@/components/live/state";

export function LiveLabel({ state, className }: { state: CardLiveState; className: string }) {
  return (
    <p className={className}>
      <span aria-hidden="true" className="break-words">
        {state.labelLead === "Not updating" ? <><span className="text-warn">{state.labelLead}</span>{state.labelRest}</>
          : state.labelLead === "Live" ? <><span className="text-text">{state.labelLead}<span className="text-text-2">{state.labelJoiner}</span></span>{state.labelRest}</>
            : state.label}
      </span>
      <span className="sr-only">{state.reader}</span>
    </p>
  );
}
