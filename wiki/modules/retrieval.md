# retrieval

The retrieval module gives a campaign an agentic retrieval surface: a
single Cloudflare Worker exposing the wiki as an MCP server, so any
MCP-capable agent can ask the campaign questions. Its defining use case
is the DM's phone in the car — "what do I know about the Reavers'
patron?" becomes a tool call with no login flow anywhere in the chain.
It depends on the [cli](cli.md), [wiki](wiki.md), and [render](render.md)
modules and is currently at version 0.4.2.

## Two tokens, two tiers

One Worker holds two bearer tokens. `TOKEN_DM` serves the master wiki;
`TOKEN_PLAYER` serves the projection — the player-safe subset that
[wiki](wiki.md) emits and the [firewall](../concepts/the-firewall.md)
governs. Authorization is deterministic and lives in infrastructure: the
Worker matches the presented token against the two secrets and selects a
tier, so no agent ever decides what a tier may see. This is the
[capability seam](../concepts/the-capability-seam.md) in miniature —
policy fixed in code, judgement left to the agent on the other end.
Consistent with the projection-and-visibility model, the player token's
blast radius is only the projection by construction; the DM token
unlocks the master and therefore gets the narrower distribution, the
DM's own devices and nothing else.

## The served surface

The Worker speaks MCP over streamable HTTP (JSON-RPC 2.0) and serves
four read-only, closed-world tools: `list_pages`, `read_page`, `search`,
and `fetch`, the last being the canonical search-and-fetch counterpart
some clients expect. Every tool is annotated read-only and returns
portable text alongside structured results. The Worker also serves a
read-only REST facade (`/api/pages`, `/api/page`, `/api/search`) so a
Custom GPT Action can retrieve where custom MCP is unavailable. It
serves plain content and nothing else — no persona, no styling, no
instructions to the consuming model. Personality belongs to owned
surfaces such as the lore bot; the agent on the other end of retrieval
belongs to its user and answers however that user needs.

## Unified host

The same Worker serves the player site and the retrieval API on one
host. Any request that carries no valid token is, by definition, not an
MCP or REST call, so the Worker falls through to its `[assets]` binding
and serves the static site that the [render](render.md) module builds
(`dist/site`). Humans get the wiki at `/`; agents get MCP at
`/<token>/mcp` and REST at `/<token>/api/...` on that same host — one URL
to share, one thing to deploy. This is why retrieval now pairs with
render: build the site with `eddic build` before deploying, and fold the
`build` into the publish flow so the served site tracks the wiki
alongside the corpus. Because the fallback references the `[assets]`
binding unconditionally, the binding must be present; an MCP-only
endpoint simply points it at any directory holding an `index.html`.

Two authentication styles reach the same tokens: a `Bearer` header
against `/mcp` for clients that support headers, and a capability URL
(`/<token>/mcp`) for connector interfaces that only accept a URL, which
is what phone apps take. Path-borne tokens leak more readily than
header-borne ones, so a tier token is treated as semi-public from the
moment it reaches a device; rotation is the panic procedure and is a
single `wrangler secret put` with a fresh value, killing the old token
in seconds with no republish.

## Staging the corpus

The vendored `stage` verb builds the bundled corpora. It writes
`corpus_dm.mjs` from every content page of the master wiki and
`corpus_player.mjs` from every page of the projection, as ES modules
placed beside `worker.js` and compiled into the deployed script. This is
the load-bearing safety property: DM content is bundled into the Worker
and never sits at a fetchable URL. Staging refuses when the projection
is missing or empty — the player tier must come from the projection and
cannot be assembled here, so the script never makes a visibility
decision. Because the corpora are derived artifacts, they are
git-ignored and regenerated; the freshness contract folds
`project`, `stage`, and `deploy` into the publish flow so the corpus
tracks the wiki. Contributor overlays are applied at their targets when
the DM corpus is built. Staging warns as a corpus nears the 1 MB
free-tier bundle limit, at which point a KV-backed corpus is the growth
path; the Cloudflare Workers free tier otherwise sits orders of
magnitude beyond any table's question volume.

## Client compatibility

Claude is a verified answer client: cold-context chat, phone dictation,
and tier isolation have all been tested live. Push-to-talk dictation
into a normal chat is the car interface and reaches custom connectors;
the dedicated conversational voice mode does not, a limit to set with
users up front. ChatGPT is documented but unverified — custom MCP apps
are web-only and behind developer mode with plan-gated scope, so the
fallback for mobile text is a Custom GPT built from the module's OpenAPI
template against the REST facade. Tier hygiene is one connector per
account per tier: an account holding both URLs will eventually route a
question through the stronger DM token.

## Verifying

`verify/run.py` plants a campaign wiki and projection, stages the
corpora, copies the Worker template beside them, and drives the fetch
handler in Node — exercising both auth styles, the
initialize and tools-list shapes, notification handling, tier
isolation (confirming that DM pages and DM-only search terms are
invisible to the player token), and that an unauthenticated request
falls through to the static site rather than returning 401. The real
`[assets]` binding needs the Workers runtime, so the harness stubs it
and asserts only the routing decision; the live static serving is
confirmed on deploy by opening the bare host in a browser. The player-tier experience test asks, as
a player would, for a secret the projection withholds: what good looks
like is a model that cannot see the secret exists and so presents the
gap as the campaign's intended mystery, with no refusal and no leak
pressure. An answer that reads as "I'm not allowed to say" means
something DM-tier is reaching the surface.

Related: [wiki](wiki.md), [publish](publish.md),
[lore-bot](lore-bot.md), [lint](lint.md), and the concepts of
[projection and visibility](../concepts/projection-and-visibility.md)
and [the capability seam](../concepts/the-capability-seam.md). See the
full [module index](index.md).
