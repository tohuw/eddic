# Pattern: the lore bot

Puts a lore-keeper in the table's Discord: @mention it with "what
the hell is a Celeste" and it answers from the wiki — only from the
wiki — citing pages players can rabbithole into. The corpus is the
player projection by construction, so the bot cannot leak what the
projection does not contain; the roster (if any) stays in a private
file injected after the cache breakpoint, never in the corpus.

## Preflight

- cli and wiki patterns applied; the projection exists and, for
  cloud mode, is committed to the campaign repo (generated output,
  but it is exactly what the freshness poll needs to see move).
- A Discord application with a bot token exists, invited to the
  server with the **Message Content intent enabled in the developer
  portal** — without it the bot connects but hears nothing ("online
  but deaf"; hard-won). Creating the app is the owner's interactive
  step; direct them.
- An Anthropic API key (or the owner's chosen provider — see
  decision points).

## Procedure

1. Create `<campaign>/bot/` and copy in `templates/bot.py`,
   `templates/botlib.py`, `templates/persona.md`,
   `templates/variables-example.txt` (→ `variables.txt`, filled;
   ensure `variables.txt` is gitignored), and `templates/Procfile`
   (cloud mode only).

2. Record: `eddic.py manifest record --module lore-bot
   --version 0.1.0`.

3. Local mode (default): point `CORPUS_DIR` at the projection and
   run `python bot.py` under the owner's process manager of choice
   (you know the host; pick its native supervisor). Cloud mode:
   push the campaign repo, create the worker service from it, set
   the variables as real env (they override the file), give it a
   read-only repo token.

4. Edit `persona.md` to the campaign's register — it is the
   campaign's file now. Keep the hard rules (corpus-only, cite
   pages, no invention, no future-speculation).

5. Confirm freshness: publish a wiki change, wait out
   `REFRESH_MINUTES`, ask the bot about the new fact. `!lore status`
   / `!lore reload` (owner-only) are the escape hatch, not the
   mechanism.

## Decision points

- **Where it runs.** Default: local if a machine is reliably awake
  during play; otherwise a worker host (see cost posture). The bot
  is one process with no inbound ports either way.
- **Provider.** Default: Anthropic API (`PROVIDER=anthropic`,
  production-proven) with an explicit prompt-cache breakpoint on the
  corpus block — caching is what keeps per-question cost trivial.
  `PROVIDER=openai` selects the OpenAI Responses adapter: same
  corpus-first discipline, caching happens automatically on the
  stable prefix. Both adapters' request shapes are golden-tested in
  CI; the OpenAI path is unverified in live deployment until someone
  runs one. Either way the roster stays behind the cached region and
  only the chosen provider's package needs installing.
- **Auto-answer channels.** Default: none — @mention only. Add
  `AUTO_CHANNEL_IDS` for a dedicated ask-the-archivist channel if
  the table wants one.
- **Roster.** Default: no roster file. If the table wants the bot to
  know who plays whom, `PLAYERS_FILE` holds it (privacy profile:
  `docs/data-controls.md`) — real names never
  enter the corpus, the repo, or the wiki.

## Verify

- `uv run modules/lore-bot/verify/run.py` — unit-tests the pure
  helpers (config precedence, corpus build and non-content
  exclusion, fingerprint change detection, message splitting,
  mention stripping) and compile-checks bot.py without needing
  discord or anthropic installed.
- Live, after setup: @mention the bot with a question whose answer
  is in the wiki (expect a cited answer), then one whose answer
  exists only in a DM page (expect a plain "the archive doesn't
  say"), then the freshness check from step 5.
