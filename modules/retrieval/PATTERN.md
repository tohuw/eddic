# Pattern: agentic retrieval (the Worker MCP)

Gives the campaign a retrieval surface any MCP-capable agent can use
— including the DM's phone in the car: "what do I know about the
Reavers' patron?" becomes a tool call against the DM tier, no login
flow anywhere in the chain. One Worker, two tokens: TOKEN_DM serves
the master wiki, TOKEN_PLAYER serves the projection. Deterministic
auth in infrastructure; no agent ever decides what a tier may see.
The worker serves plain content and nothing else — no persona, no
styling, no instructions to the consuming model (DESIGN principle
11): the agent on the other end belongs to the user and answers in
whatever way its user needs. Personality belongs to owned surfaces
like the lore bot.

## Preflight

- cli and wiki patterns applied; `eddic project` succeeds.
- Node and wrangler available — install them yourself (npx works).
- Wrangler authenticated (`wrangler whoami`). Fresh Cloudflare
  account: the human's complete list is sign up (free, no card),
  click the verification email (deploys fail on unverified
  accounts), and click **Allow** when you run `wrangler login` for
  them. If the account's first deploy errors that a workers.dev
  subdomain is needed, have them open the dashboard's Workers
  section once — visiting auto-creates it. The publish pattern's
  preflight carries the long-form version of this onboarding.

## Procedure

1. Vendor the staging verb:

       cp scripts/stage.py <campaign>/.eddic/lib/stage.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module retrieval --version 0.1.0 --verbs stage

2. Create `<campaign>/worker/`: copy `templates/worker.js` and
   `templates/wrangler.toml` (fill `{{WORKER_NAME}}`; it becomes the
   `<name>.workers.dev` subdomain). Run `eddic.py stage` — it writes
   the two corpora beside worker.js, refusing if the projection is
   missing (the player tier only ever comes from `eddic project`).
   Add `worker/corpus_*.mjs` to the campaign's `.gitignore`: the
   corpora are derived artifacts (regenerate with `eddic stage`), and
   corpus_dm.mjs concentrates every DM secret into one file — it
   belongs in the deployed Worker, not in history.

3. Generate two tokens and set them as secrets (never in files, never
   in the repo). Non-interactive, so you can drive it for the user:

       T=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
       printf %s "$T" | wrangler secret put TOKEN_DM
       # repeat with a fresh value for TOKEN_PLAYER

   Show the user their two capability URLs once, labeled (DM URL to
   the DM's own devices only; player URL shareable with the table).
   Each `secret put` cuts a new Worker version that takes a few
   seconds to reach the edge — a 401 immediately after setting a
   token is propagation, not misconfiguration; retry before
   diagnosing.

4. Deploy: `wrangler deploy` from `worker/`. Re-publish cadence: any
   time the wiki changes, `eddic.py project && eddic.py stage &&
   wrangler deploy` — fold this into the publish/routine flow so the
   corpus tracks the wiki (freshness contract).

5. Connect an agent. Two auth styles, both live:
   - `Authorization: Bearer <token>` against `https://<worker>/mcp`
     — for clients that support headers.
   - Capability URL: `https://<worker>/<token>/mcp` — for connector
     UIs that only accept a URL (this is what the phone app's custom
     connector settings take). The DM configures the DM-token URL on
     their own devices only; the player URL can be shared with the
     table.

   **Claude, route A — the user clicks it themselves** (verified
   2026-07 on claude.ai web; adding once on web syncs account-wide,
   phone included). Give them exactly this, no prose around it:

   1. Go to claude.ai → Settings → **Connectors** (it lives under
      the *Customize* section).
   2. Click **Add ▾**, then **Add custom connector**. Not "Browse
      connectors" — that is a directory of commercial vendors, and
      searching it for words like "remote" strands you at
      Remote.com.
   3. **Name**: anything ("<campaign> DM"). **Remote MCP server
      URL**: paste the capability URL. Leave Advanced settings'
      OAuth fields empty — the token in the URL is the auth.
   4. Click **Add**. It connects immediately and opens the
      connector's page.
   5. On that page, change the tool-permission dropdown from
      "Needs approval" to **Always allow** (the tools are
      read-only; approval taps kill hands-free voice use).

   **Claude, route B — you drive it for them.** Needs the Claude in
   Chrome extension installed and the user's consent to browser
   control — say that cost out loud; some users would rather make
   five clicks than install an extension. With it: open
   claude.ai settings in their browser, follow route A's path, fill
   the two fields, Add, set Always allow, and tell them what you
   did. Route A is the fallback whenever the extension isn't there.

   **ChatGPT — UNVERIFIED, written from documentation 2026-07;
   validate against a real ChatGPT before leaning on it.** Custom
   MCP servers sit behind **Developer mode**, paid plans only
   (Plus/Pro; workspace plans need an admin to allow it). The
   user's list: Settings → **Security and login** → enable
   **Developer mode** (some UIs: Settings → Apps & Connectors →
   Advanced settings); then Settings → **Apps** ("connectors" were
   renamed "apps" in Dec 2025 — older UIs say Connectors) → create
   a new developer-mode app → Name, Description (the model reads
   it — say "lore lookup for our D&D campaign"), MCP server URL =
   the capability URL, no OAuth → create, confirm the three tools
   list, enable them. Unknowns to verify: exact menu wording by
   plan, mobile availability of the add flow, and whether
   connector tools reach ChatGPT voice mode at all.

   Tier hygiene on each account: one connector, one tier. An account
   holding both URLs will sooner or later route a question through
   the DM tier — the model has no reason not to use the better
   token. Swapping a connector's tier means remove-and-re-add (the
   ⋮ menu has no edit; only "Refresh tools list" and "Remove"). Two
   claude.ai quirks seen live: the Add step sometimes lands on a
   "not connected yet" page — click **Connect**; and Connect can
   flash a "couldn't register with sign-in service / add an OAuth
   Client ID" toast even as the connector connects fine — check the
   connectors list for the checkmark before debugging anything.

6. **Rotation is the panic procedure**: `wrangler secret put
   TOKEN_DM` with a fresh value, update the connector config, done —
   old token dead in seconds, no republish. If a DM-token leak is
   suspected, rotate first and investigate second.

## Decision points

- **Player tier.** Default: enabled — players asking their own agent
  questions is half the point. A table that only wants the DM tier
  just never sets TOKEN_PLAYER (unset token = tier off).
- **Auth style.** Default: capability URL for phone connectors,
  header auth for desktop agents. Same tokens either way.
- **Voice mode.** Default: push-to-talk voice transcription into a
  normal chat — verified 2026-07 on the Claude phone app: asked a
  cold-context lore question about a term only the wiki defines,
  the model reached for search unprompted and answered in ~10 s on
  the full model. That dictation path is the car interface. The
  dedicated conversational voice mode does NOT reach custom
  connectors (verified 2026-07 — it says so itself if asked); set
  that expectation up front so nobody blames the worker. Small-model
  chat tiers handle the tools well, so retrieval quality doesn't
  hinge on the top model.

## Verify

- `uv run modules/retrieval/verify/run.py` — stages a planted
  campaign and drives the worker's fetch handler in node: 401s, both
  auth styles, initialize/tools-list shape, notification handling,
  and tier isolation (DM page and DM-only search terms invisible to
  the player token).
- After a real deploy: from an MCP client (or curl), initialize with
  each token; `search` for a DM-only term with the player token and
  confirm blindness; rotate a token and confirm the old one dies.
- The player-tier experience test: ask, as a player would, for a
  secret the projection withholds. What good looks like: the model
  can't see that the secret exists, so it presents the gap as the
  campaign's intended mystery and encourages play — no refusal, no
  leak-pressure. If the answer instead reads as "I'm not allowed to
  say," something DM-tier is reaching the surface; investigate.
