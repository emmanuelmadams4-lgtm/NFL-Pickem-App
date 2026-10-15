# Security review 1: step 8g web (Dwight `dwight-mv5mkpow`, 2026-10-15, on `91da4a9`)

PASS for step 8g web: git diff origin/main...91da4a9 in lane-web. There are no findings at CRITICAL, HIGH or MEDIUM.

WHAT I CHECKED
- I read the production diff myself: news.tsx (new), game-view.tsx, queries.ts useNews, and client.ts api.news and keys.news.
- I did not run the two ecc agents. The change is UI only and adds no new server surface. Nothing was run and no server was started.

ROUTE CONTRACT NOTES: all met
- L5: title, source, tags and the age are all React text. There is no dangerouslySetInnerHTML or innerHTML.
- L6: a link is shown only when url starts with "https://", so javascript:, data:, http: and null get plain text. The link has target=_blank and rel="noopener noreferrer".
- L10 / N1: when the server sends no items, the page says "No news for this game yet". A missing published_at shows no age.
- game_id goes through encodeURIComponent (client.ts news), so no path or query injection.
- Auth: the request goes through the existing api client, so the bearer token is sent and a 401 hits the React Query sign-out handler.
- The offline cache keeps public news headlines, like the other queries. That holds no secret and no member data.

ADVICE (LOW, not blocking)
- A1, news.tsx: the link test is case-sensitive, so a "HTTPS://" url is shown as text with no link. That fails safe; the server can lower-case the scheme if it wants.
- A2, news.tsx: tags use key={tag}. A repeated tag gives a React key warning only.

## Triage (Jim)

- A1: not taken. Fails safe; the server's R7 already returns only `https` links.
- A2: not taken. A repeated tag only gives a development-time React key warning; nothing a user sees.
- WO2 after this review only changes a class and adds an sr-only span and a separator; no new surface.
