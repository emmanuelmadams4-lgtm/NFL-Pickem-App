"use client";

import { PageHead } from "@/components/ui";
import { WeekPicker } from "@/components/pickers";
import { useGroupData } from "@/components/group/data";
import { useWeek } from "@/lib/queries";
import { useSelection } from "@/lib/selection";
import { UploadPanel } from "@/components/group/upload-panel";
import { Standings } from "@/components/group/standings";
import { Shares } from "@/components/group/shares";

export function GroupView() {
  const { season, week } = useSelection();
  const { standings, shares, reload } = useGroupData(season, week);
  const weekData = useWeek(season, week);

  return (
    <div className="space-y-8 lg:space-y-10">
      <PageHead kicker="Your Yahoo pick'em group" title="Group" aside={<WeekPicker />} />
      <UploadPanel season={season} week={week} onSaved={reload} />
      <div className="grid min-w-0 gap-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-6">
        <Standings season={season} week={week} state={standings} onRetry={reload} />
        <Shares season={season} week={week} state={shares} weekGames={weekData.data?.games} onRetry={reload} />
      </div>
    </div>
  );
}
