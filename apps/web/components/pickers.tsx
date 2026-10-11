"use client";

import { useMeta } from "@/lib/queries";
import { useSelection } from "@/lib/selection";
import { Button, SelectField, cx } from "@/components/ui";

export function SeasonPicker({ className }: { className?: string }) {
  const meta = useMeta().data;
  const { season, setSeason } = useSelection();
  if (!meta) return null;
  return (
    <SelectField label="Season" className={className} value={season} onChange={(e) => setSeason(Number(e.target.value))}>
      {meta.seasons.map((s) => (
        <option key={s} value={s}>
          {s}
        </option>
      ))}
    </SelectField>
  );
}

/** Season, previous/next week and a week jump. Lives in the top bar on desktop and in the page on phones. */
export function WeekPicker({ className }: { className?: string }) {
  const meta = useMeta().data;
  const { season, week, setSeason, setWeek } = useSelection();
  if (!meta) return null;
  const weeks = meta.weeks;
  const idx = weeks.indexOf(week);
  const step = (d: number) => {
    const n = weeks[idx + d];
    if (n !== undefined) setWeek(n);
  };
  return (
    <div className={cx("flex items-center gap-2", className)}>
      <SelectField label="Season" value={season} onChange={(e) => setSeason(Number(e.target.value))} labelClassName="hidden xl:inline">
        {meta.seasons.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </SelectField>
      <div className="flex items-center gap-1">
        <Button size="sm" variant="ghost" aria-label="Previous week" disabled={idx <= 0} onClick={() => step(-1)} className="w-9 px-0 max-lg:h-10 max-lg:w-11 max-lg:border-border max-lg:bg-elevated">
          <span aria-hidden className="text-lg leading-none">&lsaquo;</span>
        </Button>
        <SelectField label="Week" value={week} onChange={(e) => setWeek(Number(e.target.value))} hideLabel>
          {weeks.map((w) => (
            <option key={w} value={w}>
              Week {w}
            </option>
          ))}
        </SelectField>
        <Button size="sm" variant="ghost" aria-label="Next week" disabled={idx >= weeks.length - 1} onClick={() => step(1)} className="w-9 px-0 max-lg:h-10 max-lg:w-11 max-lg:border-border max-lg:bg-elevated">
          <span aria-hidden className="text-lg leading-none">&rsaquo;</span>
        </Button>
      </div>
    </div>
  );
}
