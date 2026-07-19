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
   `<name>.workers.dev` subdomain). The template's `[assets]` binding
   points at `../dist/site` (the render module's `site_dir`) so the
   Worker serves the player site on the same host — build it with
   `eddic build` before deploying. Run `eddic.py stage` — it writes
   the two corpora beside worker.js, refusing if the projection is
   missing (the player tier only ever comes from `eddic project`).
   The worker serves four read-only tools — list_pages, read_page,
   search, and fetch (the canonical search+fetch counterpart some
   clients expect) — all annotated read-only and closed-world, with
   portable text plus structured results.
   Add `worker/corpus_*.mjs` to the campaign's `.gitignore`: the
   corpora are derived artifacts (regenerate with `eddic stage`), and
   corpus_dm.mjs concentrates every DM secret into one file — it
   belongs in the deployed Worker, not in history.

3. Generate two tokens and set them as secrets (never in files, never
   in the repo). Non-interactive, so you can drive it for the user:

       T=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
       printf %s "$T" | wrangler secret put TOKEN_DM
       # repeat with a fresh value for TOKEN_PLAYER

   Token hygiene (`wiki/reference/data-controls.md` has the full profile):
   when you can configure the consuming client directly (a
   consented browser session, a config file you write), do that and
   never print the token at all; when the user must paste, show each
   URL once, labeled (DM URL to the DM's own devices only; player
   URL shareable with the table), and refer to tokens afterward by
   fingerprint (first 8 characters). Anything that lands a token in
   a transcript, screenshot, or log gets rotated on sight. Each
   `secret put` cuts a new Worker version that takes a few seconds
   to reach the edge — a 401 immediately after setting a token is
   propagation, not misconfiguration; retry before diagnosing.

4. Deploy: `wrangler deploy` from `worker/`. Re-publish cadence: any
   time the wiki changes, `eddic.py project && eddic.py build &&
   eddic.py stage && wrangler deploy` — the `build` keeps the served
   site fresh alongside the corpus; fold this into the publish/routine
   flow so both track the wiki (freshness contract).

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
   the live test is `verify/chatgpt-acceptance.md`, and nothing
   here becomes a promise until it passes.** Custom MCP apps are
   **web-only** and sit behind **Developer mode**; scope is
   plan-gated (Pro gets read/fetch-style MCP in developer mode;
   full custom MCP is Business/Enterprise/Edu, where an admin must
   allow it — document the user's plan before promising the route).
   Mobile apps and ChatGPT Voice do not run custom MCP at all; for
   mobile text on Plus, use the Custom GPT Actions route instead.

   Route A, the user clicks (web): Settings → enable **Developer
   mode** (under Security-and-login or Apps & Connectors →
   Advanced, wording varies); then Settings → **Apps** ("connectors"
   were renamed "apps" Dec 2025) → create app → Name, Description
   (the model reads it — say what the corpus answers), MCP server
   URL. Auth: prefer **bearer app auth** if the dialog offers a
   token/header field — the token stays out of the endpoint URL —
   and fall back to the capability URL when it doesn't. Create,
   confirm the four tools, enable them. Route B, you drive it via
   the user's browser with their consent, same path, same caveat as
   the Claude route B.

   **ChatGPT on Plus / mobile text — Custom GPT Actions
   (UNVERIFIED, same acceptance rig).** The worker also serves a
   read-only REST facade (`/api/pages`, `/api/page?id=`,
   `/api/search?q=`) so a Custom GPT can retrieve where custom MCP
   is unavailable. Build one GPT per tier, never both in one: create
   a GPT (Plus or above) → Configure → Actions → import
   `templates/openapi.json` (fill `{{WORKER_URL}}`) → Authentication
   = API key, **Bearer**, paste that tier's token (the token stays
   out of URLs here) → paste the matching instructions template
   (`chatgpt-player-instructions.md` or `chatgpt-dm-instructions.md`,
   fill `{{SITE_NAME}}`). The player GPT can be link-shared with the
   table; the DM GPT must never be shared — its key unlocks the
   master. Works in web and mobile **text**; Actions do not run in
   ChatGPT Voice — say so up front.

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
   suspected, rotate first and investigate second. Doctrine: treat a
   tier token as **semi-public from the moment it reaches a device**
   — path-borne tokens leak more readily than header-borne ones
   (logs, screenshots, pasted links, share sheets). The player
   token's blast radius is only the projection, by construction —
   that is the architecture doing its job. The DM token's is the
   master, so it gets the narrower distribution: the DM's own
   devices, nothing else, ever.

## Decision points

- **Player tier.** Default: enabled — players asking their own agent
  questions is half the point. A table that only wants the DM tier
  just never sets TOKEN_PLAYER (unset token = tier off).
- **Auth style.** Default: capability URL for phone connectors,
  header auth for desktop agents. Same tokens either way.
- **Unified host — serve the player site from the Worker.** Default:
  on. One host, one URL to share: humans get the player site at `/`,
  agents get MCP at `/<token>/mcp` (and REST at `/<token>/api/...`) on
  the same host. Any request without a valid token is, by definition,
  not an MCP/REST call, so the Worker falls through to its `[assets]`
  binding (`directory = "../dist/site"`, `binding = "ASSETS"`) and
  serves the render module's built site. Two consequences: build
  before you deploy (`eddic build` must have populated `site_dir`),
  and the `[assets]` binding must be present — the fallback references
  it unconditionally, matching the proven-live worker. This is why
  retrieval now pairs with render: the site the Worker serves is the
  same static mirror render produces. If a campaign genuinely wants an
  MCP-only endpoint, point `[assets]` at any directory holding an
  `index.html` (even a one-line placeholder); leaving the binding out
  breaks unauthenticated requests.
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
- **Custom domain.** Default: the `<name>.workers.dev` host works out
  of the box. A custom domain (e.g. `campaign.example.com`) gives a
  stable, memorable MCP URL — but the zone's security then sits in
  front of the Worker, and **Cloudflare's AI-bot controls block MCP
  connectors**: the connector fetches with the `Claude-User` /
  `ChatGPT-User` user-agent, which "Block AI bots" / Bot Fight Mode
  `403`s — while a browser and curl pass, so the block is invisible to
  ordinary testing (test with `curl -A Claude-User`, not a bare curl).
  On the zone, set Cloudflare's AI-bot policy Agent = **Allow** and
  disable the legacy "Block AI bots" rule for the worker host — this is
  a domain built to serve agents. (Connectors also require CORS on
  every response and `/.well-known/oauth-*` returning `404` not `401`,
  so the client uses the URL token instead of attempting OAuth
  registration — both handled by the worker template as of 0.4.1.)

## Verify

- `uv run modules/retrieval/verify/run.py` — stages a planted
  campaign and drives the worker's fetch handler in node: both auth
  styles, initialize/tools-list shape, notification handling, tier
  isolation (DM page and DM-only search terms invisible to the player
  token), and that an unauthenticated request falls through to the
  static site rather than 401ing. The real `[assets]` binding needs
  the Workers runtime, so the harness stubs it with a sentinel and
  asserts only the routing decision (no valid token => serve the
  site) — the live static serving is confirmed on deploy, below.
- After a real deploy: open the bare host in a browser and confirm the
  player site loads (unified host serving `[assets]`); from an MCP
  client (or curl), initialize with each token; `search` for a DM-only
  term with the player token and confirm blindness; rotate a token and
  confirm the old one dies.
- The player-tier experience test: ask, as a player would, for a
  secret the projection withholds. What good looks like: the model
  can't see that the secret exists, so it presents the gap as the
  campaign's intended mystery and encourages play — no refusal, no
  leak-pressure. If the answer instead reads as "I'm not allowed to
  say," something DM-tier is reaching the surface; investigate.
