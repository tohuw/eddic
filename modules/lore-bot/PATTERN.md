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
- A Discord application with a bot token, invited to the server.
  Assume the owner has never made a Discord bot. The flow (portal
  layout verified 2026-07): sign in at
  discord.com/developers/applications, then —

  1. **New Application** → name it (the table sees this name) →
     Create.
  2. Left nav **Bot** → **Reset Token** → the token shows **once**;
     it goes straight into `variables.txt`, nowhere else. Lost or
     leaked token = Reset Token again (that is also the rotation
     procedure — old token dies instantly).
  3. Same Bot page: enable **MESSAGE CONTENT INTENT** and save.
     This is the trap: it is a privileged toggle, off by default,
     and without it the bot connects but hears nothing — "online
     but deaf" (hard-won). Check this FIRST when the bot ignores
     everyone.
  4. Left nav **OAuth2** → URL Generator: scope `bot`; permissions
     View Channels, Send Messages, Read Message History, Add
     Reactions. Open the generated URL, pick the server, Authorize.

  You can drive steps 1–4 through the owner's browser with their
  consent (the connector playbook in the retrieval pattern):
  everything is clickable except their Discord login and the final
  Authorize confirmation, which are theirs. When you drive, read
  the token off the portal page directly into `variables.txt` and
  never echo it into the conversation (data-controls doctrine).
  Self-serve fallback: hand them the four steps above verbatim,
  and have them paste the token into `variables.txt` themselves.
- An Anthropic API key (or the owner's chosen provider — see
  decision points). Same handling: into `variables.txt`, never into
  chat.
- A server to test in before the table's real one: a throwaway
  Discord server is one click (the **+** at the bottom of the
  server list → Create My Own) and lets the whole loop run without
  an audience.

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
   (you know the host; pick its native supervisor). Run it
   unbuffered (`PYTHONUNBUFFERED=1`) — otherwise the startup and
   reload prints sit invisibly in the stdout buffer and the bot
   looks silent precisely when you are trying to watch it. Cloud mode:
   push the campaign repo, create the worker service from it, set
   the variables as real env (they override the file), give it a
   read-only repo token.

4. The persona is the campaign's file now, and its default — the
   courteous, dry-witted chronicler — stands perfectly well on its
   own. Tell the owner plainly: **the bot's character is theirs to
   change by just telling you what they want.** "Make it talk like
   a goblin" is a complete instruction — write the voice yourself;
   that is your craft, not a template's. Whatever the character,
   the hard rules stay (corpus-only, real citations, no invention,
   no future-speculation, length caps) — personality rides on top
   of them, never instead of them — and log persona changes as
   `schema`. Know the seam: the
   persona file is the owner's voice and nothing else; config-derived
   facts are appended by bot.py at runtime (with `SITE_URL` set, a
   citation line carrying the live site root and a worked example
   joins the persona block every startup). Change the config, not
   the prose, when plumbing moves — and expect the running system
   prompt to be persona + that line.

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
  `wiki/reference/data-controls.md`) — real names never
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
