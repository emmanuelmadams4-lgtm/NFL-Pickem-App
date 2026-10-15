"use client";

import { ago, type GameDetail } from "@nflpi/shared";
import { useNews } from "@/lib/queries";
import { Chip, ErrorState, Section, Skeleton } from "@/components/ui";

export function NewsSection({ game }: { game: GameDetail }) {
  const news = useNews(game.game_id);

  return (
    <Section id="news" title="News">
      {news.isPending && !news.data ? (
        <Skeleton className="h-24 w-full" />
      ) : news.isError && !news.data ? (
        <ErrorState title="Could not load news" error={news.error} onRetry={() => news.refetch()} />
      ) : !news.data?.items.length ? (
        <p className="text-sm text-text-2">No news for this game yet.</p>
      ) : (
        <ul className="divide-y divide-border">
          {news.data.items.map((item, index) => (
            <li key={index} className="min-w-0 py-4 first:pt-0 last:pb-0">
              {item.url?.startsWith("https://") ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block break-words text-sm font-medium text-text underline underline-offset-2"
                >
                  {item.title}
                </a>
              ) : (
                <p className="break-words text-sm font-medium text-text">{item.title}</p>
              )}
              <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-subtle">
                <span>{item.source}</span>
                {item.published_at && <span>{ago(item.published_at)}</span>}
              </div>
              {item.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {item.tags.map((tag) => <Chip key={tag}>{tag}</Chip>)}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
