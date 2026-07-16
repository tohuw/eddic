# Observation: chain wiki publish → Snorri reload

*From the dnd project, 2026-07-15.*

Snorri's corpus load is startup-time: `build_corpus()` fetches a fresh
tarball of `tohuw/dnd` every time the process starts, so a Railway
restart/redeploy is exactly equivalent to `!snorri reload`. But the two
deploy pipelines are disconnected: Railway watches only the snorri repo,
and the wiki publishes via `publish.sh` in the dnd repo (Cloudflare
Pages). Result: every wiki publish leaves Snorri stale until someone
remembers to say `!snorri reload` in Discord.

Worth closing that gap — either chain the deploys or add a hook so a
wiki publish implies a reload.

## Constraints discovered

- Snorri has no HTTP server (pure gateway bot), so there's no endpoint
  for a GitHub webhook or `publish.sh` to hit as-is.
- A hook can't just post `!snorri reload` via the `snorri.py` REST CLI:
  `bot.py` ignores all bot-authored messages (`message.author.bot`
  check, bot.py:209) and gates `reload` to `OWNER_ID` anyway
  (bot.py:240).

## Feasible shapes

1. **Chain in `publish.sh`** — after the Cloudflare deploy, trigger a
   Railway service restart via the Railway CLI/API
   (`railway redeploy` / GraphQL). Simple, no bot changes; couples the
   dnd repo to Railway credentials.
2. **Self-refreshing bot** — Snorri polls GitHub for the HEAD SHA of
   `tohuw/dnd` master (cheap API call, the PAT already covers it) and
   rebuilds the corpus when it changes. No coupling, no secrets in the
   dnd repo; wiki freshness bounded by poll interval. Probably the
   cleanest.
3. **Tiny HTTP listener in the bot** — aiohttp endpoint on Railway's
   assigned port receiving a GitHub push webhook (or a curl from
   `publish.sh`), verified by shared secret, calls `build_corpus()`.
   Most immediate, most new surface area.

Option 2 also fixes the case where wiki edits land via any path other
than `publish.sh` (direct pushes, future automation).
