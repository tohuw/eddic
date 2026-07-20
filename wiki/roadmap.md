# Roadmap

This page is Eddic's module queue and its deferred decisions. The order was
chosen so that each step exercises what the previous one built: the first
module proves the [module contract](concepts/the-module-contract.md), and the
`eddic` CLI grows verbs only as later modules need them.

## Status

**2026-07-16:** items 1–8 shipped at 0.1.0 (see the
[module index](modules/index.md)), plus repository CI enforcing the contract
floor and running every module verify on ubuntu/macos/windows. Retrieval is
proven live end-to-end on a Land of Song test absorption: the Worker deployed,
tier isolation wire-verified, and the voice spike passed — push-to-talk
dictation on the phone app reached connector tools and answered from a cold
context in about ten seconds. The Pages live deploy awaits the owner.
Remaining at that point: recorder (9, needs the owner's brief), discord-setup
(10), routines (11), orlog (12).

**Provider parity, 2026-07-17** (issue #1, PRs #2–#9 merged): the compatibility
ledger (`docs/compatibility.md`) with floor-enforced, evidence-backed vendor
claims; worker 0.3.0 (cross-client MCP hardening plus a Custom GPT Actions REST
facade); lore-bot 0.2.0 (an OpenAI Responses adapter behind a provider seam,
the Anthropic default unchanged); data-control profiles; and Codex plugin
routing to AGENTS.md. Awaiting live vendor sessions: the ChatGPT acceptance rig
(`modules/retrieval/verify/chatgpt-acceptance.md`), a Codex plugin-install
test, and an OpenAI-provider bot deployment.

**Lore bot live, 2026-07-18:** full end-to-end on the test campaign — the
Discord app created via a driven browser (the human supplied one captcha, one
MFA, one ToS, one Authorize), corpus answers with linked citations into the
live Pages site, projection blindness holding conversationally, and the
freshness poll observed reloading unprompted after a wiki edit. Four live finds
shipped back into the module during the test.

**Overnight, 2026-07-18:** orlog (12) and routines (11) shipped at 0.1.0 —
twelve modules in the tree, queue items 1–12 all built. The Eddic site went
live at eddic-site.pages.dev (pitch, how-it-works, modules, principles, and the
privacy posture the recorder's consent post links — its trigger, fired),
dogfooded through the render module. Windows CI caught two real portability
bugs in orlog before any user could (shlex path mangling; cp1252 unable to
print "Ørlǫg"). The recorder build was deliberately deferred to a session with
the owner awake: voice capture needs live testing, lore-bot-style.

**Transaction arc, 2026-07-18:** contribs (14) and companion (13) shipped at
0.1.0; the author role is declared config (it may differ from the DM — the
[principles](design/principles.md) record the consequences); wiki 0.3.0 applies
contributor overlays across every
surface, lint 0.3.0 checks them, retrieval 0.4.0 stages the effective corpus;
`eddic bundle` is the sale-build fence (hash-pinned consent, derivation-graph
rights, stale-clearance refusal). `tools/verify_e2e.py` proves the full
composition in CI on all three OSes. Companion conduct claims are unverified
until live adversarial passes; marketplace (15) waits on the payment-gateway
decision.

## Module queue

1. **lint** — the wiki health check, generalized from the DitD discipline:
   broken links and anchors, orphans, catalog drift, STUB mismatches, malformed
   log headers, and the [firewall](concepts/the-firewall.md) check (no
   player-visible page links DM-only). Deterministic reporter plus a
   model-triage seam. First because it is self-contained, high-value, and
   exercises the whole module contract.
2. **cli** — the `eddic` skeleton (uv-run Python, PEP 723): `doctor`, `lint`,
   `manifest`. The contractual locus everything else hangs off.
3. **wiki** — the campaign knowledge schema, generalized from the Land of Song
   kb: taxonomy, encyclopedia tone, stub convention, typed log, authorship
   frontmatter, visibility frontmatter, and the `project` verb (deterministic
   player [projection](concepts/projection-and-visibility.md)).
4. **render** — the purpose-built static renderer, patterned on bolverk's wiki
   stage but Eddic-owned: markdown tree in, HTML mirror out, `.md`→`.html` link
   rewriting, one template. Held at exactly that scope — the moment it grows an
   index generator, we have rebuilt Hugo badly.
5. **publish** — Cloudflare Pages deployment for the projected sites (unlisted,
   noindex; DM and player sites).
6. **retrieval** — the Cloudflare Worker MCP: bearer-token-gated, the DM token
   sees the master, the player token sees the projection; token rotation as the
   panic procedure. Includes the spike: verify connector availability in phone
   voice mode before this becomes load-bearing. Later: the `witness` write tool
   and inbox (bidirectionality).
7. **lore-bot** — snorri absorbed and parameterized: corpus-in-cached-prompt
   Discord Q&A over the player projection, a forum CLI, session announce. Must
   satisfy the [freshness contract](design/principles.md) from day one: the bot self-refreshes
   by watching the projection's version (HEAD poll) rather than relying on
   deploy chaining, webhooks, or an owner-gated reload command — the source
   stack's bot went stale on every wiki publish for lack of exactly this.
8. **transcriber** — local session transcription (whisper.cpp) from recorded
   audio; the free path that replaces paid transcript services. Likely the
   first binary-bearing module.
9. **capture** — SHIPPED 0.1.0 (2026-07-18, reframed from "recorder" at the
   owner's direction): session audio by the table's chosen route — **free Craig
   by default** (all Eddic truly needs is the audio; transcription is local;
   premium Craig with its own transcripts is equally fine), with deterministic
   staging (`eddic stage-craig`, including the folder-named-.flac quirk) and a
   no-folder-navigation agent handoff. The **recorder module** (SHIPPED 0.1.0
   the same day) is the consent-gated no-third-party option: DAVE receive was
   SOLVED here 2026-07-18 — davey plus five import-time patches to py-cord 2.8.0
   (the approach shared with upstream's in-progress PR), live capture and
   transcription proven; the patch module retires when pycord#3139 merges. Prior
   blocked-status context: Discord voice receive is broken
   Python-ecosystem-wide by DAVE E2EE enforcement; the module ships when
   Pycord-Development/pycord#3139 lands and a live capture passes. Everything
   human-facing was proven live (consent flow, commands, staging — see the
   [recorder learnings](reference/recorder-learnings.md); cloud/R2 design in the
   [cloud-recorder plan](reference/cloud-recorder-plan.md)); no module ships non-working capture, because
   modules hold only what is proven to work. The brief (owner, 2026-07-18;
   **revised the same day: the recorder is its own bot**, reversing the earlier
   one-bot call): the lore bot is always-on and cloud-cheap; the recorder is
   session-time-only and voice-heavy, wants to run beside the disk the
   transcriber reads, and cloud voice-UDP is unverified — different lifecycles,
   different hosts, so separate applications and tokens. The capability code
   shape, consent machinery, and staging layout are unchanged; the driven portal
   flow makes the second app cheap. Local, session-time execution is the
   default; the R2/cloud design (the [cloud-recorder plan](reference/cloud-recorder-plan.md)) becomes this
   bot's optional cloud mode. Audio arrives over the Discord voice gateway (no
   OS mic permission); the voice sink runs on its own thread writing straight to
   disk so answer latency can never drop frames. Summon/dismiss via slash
   commands (`/record start|stop|help`; invites need the `applications.commands`
   scope alongside `bot`). Output: per-speaker FLAC to the campaign's local disk
   in the transcriber's expected layout; on stop, files are staged and a log
   entry written — transcription stays a deliberate maintenance step. Consent:
   on start, the bot posts in the voice channel's text chat — announcement,
   privacy-posture link (hosted on the Eddic site), and per-member opt-in
   reacts; a member's audio is captured only after their react, nobody is gated
   on anyone else, and fail-closed means un-reacted members are simply never in
   the recording. Decision point: strict per-session reacts (default) vs
   standing acks remembered across sessions with visible opt-out. Doctrine:
   consent-to-record is not consent-to-sell — the transaction arc's full-table
   sign-off remains its own later act. See the [recorder](modules/recorder.md)
   module.
10. **discord-setup** — SHIPPED 0.1.0 (2026-07-18, same-day from spec to
    live-proven: mock-verified in CI, then dumped, drift-reported,
    403-refused-with-advice, re-invited, applied, and converged against a real
    server — privacy overwrites round-trip in the dump). The spec: a
    deterministic REST script as an eddic verb, using the campaign bot's
    existing token (no gateway, no second bot) against a **standing server
    spec** versioned in the campaign repo — re-running reconciles the live
    server to spec and reports drift, lint-style. The default scaffold
    generalizes the reference table's server: an ask-the-archivist channel,
    threaded session-recaps, a botspam sandbox, a session voice channel with its
    text chat, a DM-private channel, DM/player roles with sane overwrites. Ships
    a **curated third-party set** (drafted from the reference server, owner to
    confirm: dice = Avrae, scheduling = Apollo, music = Jockie; recording
    deliberately absent — the recorder capability replaces it) with the
    agent-driven invite-URL flow for each and per-bot config notes. Decision
    points: adopt-vs-scaffold on an existing server; which curated bots to take;
    spec-drift policy (report-only vs repair).
11. **routines** — the maintenance routine contract (idempotent, safe to miss,
    safe to double-run) with the preference chain: hosted agent routines →
    GitHub Actions → local cron-esque. Adapters stated as contracts, not how-tos
    (no egg-sucking).
12. **orlog** — guidance for driving Ørlǫg's headless CLI (M5, shipped
    2026-07-16: `orlog apply/dump/query/fork/validate/schema`, constraint-checked
    all-or-nothing writes, a JSON Schema of the Mutation union, zero build step
    on Node ≥ 24): the reconciler skill (wiki facts → validated mutations on a
    fork), and `validate` as the story's test suite. Unblocked.
13. **companion** — the at-the-table module family under the knowledge-parity
    conduct doctrine ([principles](design/principles.md): "Companions at the table"): player and DM
    companions on their respective retrieval tiers, and the backstory
    interviewer with its scribe/drafter authorship dial. Conduct claims verified
    adversarially per answer client before any default.
14. **contribs** — the transaction arc's machinery ([principles](design/principles.md): "The transaction
    arc"), landing as wiki/lint/publish extensions: contributor overlays with
    `replaces:` shadowing, a `derived-from:` derivation graph, the pure-corpus
    projection with its full = pure + attribution-log invariant, the
    transactability frontmatter axis and sale-build fence, consent receipts.
    Attribution *capture* ships earlier in the wiki schema — it cannot wait,
    because attribution is unrecoverable after the fact. See the
    [contribs](modules/contribs.md) module.
15. **marketplace** — transactable campaigns as products: the author role, base
    and deluxe (session-log) offerings, packaging and refusal machinery. The
    payment gateway is a deferred decision below.

**Contributable thereafter:** VTT modules (Roll20, Foundry, …) by community PR
under the contract.

## Deferred decisions, with triggers

- **Signed binaries.** Now: CI builds unsigned per-OS binaries as release
  artifacts (prove the pipeline early; agent-driven installs mostly dodge
  Gatekeeper/SmartScreen, which key on browser-download provenance). Trigger to
  buy signing (Apple Developer ~$99/yr plus notarization; Azure Trusted Signing
  ~$10/mo for Windows): a human browser-download path, or a module needing
  stable OS-permission identity.
- **License.** Resolved 2026-07-17: Apache-2.0 (see `LICENSE` and the "License
  and authorship" section of `README.md`). Permissive, so vendored and stamped
  copies inside campaign repos stay clean; it carries a patent grant; §5 makes
  inbound contributions self-licensing with no CLA needed.
- **Compression accelerators.** headroom/thlibo guidance lands inside the
  routines and transcriber modules as decision points with heuristics, per the
  [principles](design/principles.md) — never as dependencies.
- **Eddic website.** First trigger fired 2026-07-18: live at
  eddic-site.pages.dev (source in `site/`, rendered by the render module),
  carrying the privacy posture the recorder's consent post links. The
  real-domain call is now resolved: the site is live at **eddic.quest** (apex +
  www, proxied, alongside eddic-site.pages.dev). Remaining owner call: whether
  the site grows a docs/marketplace face beyond the current five pages.
- **Payment gateway.** Choose when the marketplace module (15) starts: a gateway
  with checkout-and-download and no inventory overhead; cost posture per
  principle 4. Until then the transaction arc is rights machinery, not commerce.
- **Multi-tenant lore bot (convene).** Today one bot serves one campaign:
  [convene](modules/convene.md) counts *every* scheduled event on the guild
  toward that campaign's quorum. Two campaigns sharing a Discord server would
  cross-contaminate — each other's events, reminders, and quorum counts. The
  seam is already cut the right way: convene scopes players by a per-campaign
  role (`SESSION_ROLE_ID`/`PLAYER_ROLE`), so the missing piece is scoping
  *events* the same way — a campaign only tracks events it owns. Trigger: a
  second campaign wanting to share one server (or one bot process). Likely
  shape: tag events to a campaign (an event-role gate, a channel/category
  binding, or a naming prefix) and filter `fetch_scheduled_events()` by it, with
  the lore-bot corpus and recap thread already per-campaign. Do not half-build it
  before the second tenant is real — the single-tenant path must stay
  zero-config.
- **eddic.quest subdomain hosting (multi-tenant hosting service).**
  Self-hosting is and stays the default — a campaign is a self-contained repo
  the owner controls on their own domain (or a free Pages/Workers deploy). This
  is a convenience for people who won't buy or manage a domain: give a tenant
  `<campaign>.eddic.quest` with their site, retrieval/MCP endpoint, and other
  services all hung off that one subdomain. Proven at N=1
  (`landofsong.eddic.quest` runs a real campaign's retrieval Worker plus site
  today); the decision is how to generalize to arbitrary tenants correctly. This
  is the convene multi-tenant problem widened — from one bot over many campaigns
  to one platform over many campaigns on shared `eddic.quest` infrastructure —
  and it reuses the same isolation seam: hard per-tenant separation of corpus
  and DM/player tokens, the firewall enforced across tenants so A can never read
  B. Likely shape: wildcard `*.eddic.quest` DNS plus wildcard TLS, a routing
  Worker mapping `<tenant>` to that tenant's Pages site, retrieval Worker, and
  tokens, and automated provisioning (create the campaign dir, stage the corpus,
  deploy, mint tokens, add the DNS/route — one flow). Open questions: per-tenant
  Workers vs one shared multi-tenant Worker (isolation vs cost/ops);
  token/secret management at scale (today tokens are per-Worker Cloudflare
  secrets); cert strategy (wildcard vs per-hostname custom domains); billing,
  quotas, and abuse limits if it is a real service; and how tenants author
  content (the same agent-applied module flow as self-hosted). Non-negotiable: a
  hosted tenant must always be able to walk away with their self-contained repo
  — hosting is a convenience, never lock-in. Trigger: a second party wanting to
  run a campaign without owning a domain, or demand for hosted onboarding.
- **Private / off-the-web campaigns (Cloudflare Access).** Today a campaign's
  projected sites are unlisted and noindex, and the player retrieval token
  exposes exactly the public-wiki content — so URL-only reachability is a
  deliberate, low-sensitivity default (a leaked player token reveals nothing
  the public site doesn't). Some tables will want the whole campaign *off* the
  unauthenticated web: no publicly reachable site, retrieval gated behind real
  identity. Cloudflare Access (Zero Trust) is the fit — an identity gate (email
  OTP, Google, etc.) in front of the Pages site and/or the Worker so only the
  table's members reach it, layered on the same hostnames Eddic already
  provisions. Likely shape: an Access application over the campaign hostname
  (and paths) with an allowed-emails/allowed-domain policy; agents reach the
  retrieval Worker either via Access **service tokens** or by keeping the
  capability-token path as an Access bypass (bearer and Access coexist). Open
  questions: how a claude.ai connector authenticates through Access (service
  token vs a bypass rule on `/<token>/mcp`); whether to gate the whole campaign
  or just the DM tier; and the free-tier Access seat limits for a table-sized
  group. Non-negotiable: it stays a bolt-on over the self-contained repo —
  turning it off returns the campaign to the plain unlisted default. Trigger: a
  table wanting a campaign not reachable by URL alone.
- **Agentic ("Claude") lint routine.** **Shipped v1 — lint 0.4.0 + routines
  0.2.0:** a deterministic `semantic_review.py` scaffold builds a reproducible
  review packet (master pages, plus the player projection gathered *separately*
  for firewall-in-prose) with a pinned findings schema; the routines contract
  packages the agent pass as a safe-to-miss/double-run routine; findings file
  into the witness inbox as `suggest_edit`s (or a plain report). Kept
  agent-agnostic — no unbacked vendor claim. The hosted-cloud runner is now
  wired (routines 0.3.0): a campaign vendors the `semantic-review` verb + a
  `.mcp.json` witness server + a `.claude/` recipe, and the routine runs as a
  scheduled Claude Code Routine that files findings into the witness inbox (PR
  fallback if the MCP host is domain-blocked). Remaining: the first live LLM
  pass on a real campaign, and cadence/cost tuning. Original framing: the
  [lint](modules/lint.md)
  module is a deterministic reporter with a stated model-triage seam; the
  [routines](modules/routines.md) module gives the idempotent,
  safe-to-miss/safe-to-double-run contract to hang recurring maintenance off.
  The gap between them is a packaged **agent-run semantic lint**: a routine that
  turns an LLM (Claude today) loose on the campaign the way a careful maintainer
  would, catching what regex cannot — prose that leaks DM-adjacent knowledge
  past the [firewall](concepts/the-firewall.md) without tripping the structural
  check, encyclopedic/tonal drift, facts contradicted across pages, orphaned or
  dangling narrative references, naming inconsistency, stubs that outgrew their
  marker. Output is advisory: a report the owner acts on, never an auto-rewrite
  (authorship doctrine — agent proposes, human disposes; no stylistic rewrites
  of human prose). Likely shape: a routine that fans the wiki/projection through
  a model pass against a checklist and emits findings with page anchors — and if
  the writeable MCP below lands, files them as suggested edits rather than a
  flat report. Open questions: cost and cadence (between-sessions vs on-demand),
  and keeping it from re-litigating what the deterministic floor already
  guarantees. Trigger: a campaign large enough that manual consistency review
  stops scaling.
- **Writeable retrieval (the `witness` write path).** **Shipped v1 — retrieval
  0.6.0, eddic 0.8.0.** When the campaign binds an `INBOX` KV namespace, the
  Worker exposes four MCP tools: `suggest_edit` and `suggest_page` let any tier
  **drop a proposed edit or addition** into a pending review inbox (never canon,
  and no corpus validation — so a player cannot use `suggest_edit` as an
  existence oracle on DM pages), while DM-tier-only `list_suggestions` /
  `resolve_suggestion` triage it, the gating enforced in the handler and not
  merely hidden from `tools/list`. `eddic suggestions` materializes the queue
  into a gitignored `suggestions/` dir for the owner to apply and commit; with no
  INBOX binding the campaign stays read-only. Non-negotiable held: nothing an
  agent submits reaches a player-visible or canon surface without the owner's
  explicit acceptance. Remaining: abuse / rate limits once player tokens can
  write; deeper [contribs](modules/contribs.md) attribution so an accepted
  suggestion carries hash-pinned authorship; an accept→auto-materialize path
  (today the verb stages, the owner applies); and pairing with the agentic lint
  routine above so it files its findings the same way.
- **Eddic is not D&D-specific.** Eddic grew out of a D&D campaign and its
  framing still says "D&D" throughout (AGENTS.md, the [principles](design/principles.md), the site, the
  self-documenting wiki), but the machinery — the campaign knowledge
  architecture, the deterministic player projection, retrieval, the lore/session
  bots, the session lifecycle, publishing — is system-neutral: it manages a
  collaboratively-authored world and the comms around it, not rules. Direction:
  generalize the framing to tabletop RPG campaigns broadly, auditing docs, wiki,
  and examples for hard D&D assumptions (the verify fixtures' invented world —
  the Warden, the Sunken City — are already system-neutral and stay).
  System-specific content (rules, dice mechanics, an SRD) is always an optional
  pluggable pack, never core — the reason the 5.2 SRD stays out of the tree.
  Open question: how far to generalize — Eddic assumes a GM/player split and a
  wiki-able setting, which fits most TTRPGs but not rules-light or GM-less
  systems, so decide whether to scope to "GM-led TTRPGs" or widen the
  projection/firewall model. Trigger: a non-D&D campaign adopting Eddic, or a
  public positioning pass that shouldn't over-index on one system.

## Related pages

The roadmap sits alongside the full [module index](modules/index.md) and the
[concepts index](concepts/index.md). Its versioning discipline is described
under [releases and versioning](concepts/releases-and-versioning.md); the floor
every queued item had to clear is the
[module contract](concepts/the-module-contract.md); and the tiebreaker
[principles](design/principles.md) shape which deferred decisions convert when.
Return to the [Eddic overview](index.md) for the project as a whole.
