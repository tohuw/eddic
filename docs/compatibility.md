# Compatibility — who does what, with evidence

Eddic is agent-agnostic, but "agent" hides three roles that different
products fill differently. Claims in this repo separate them:

- **Maintaining agent** — the coding agent that applies patterns and
  maintains a campaign (Claude Code, Codex, Cursor). Reads AGENTS.md.
- **Answer client** — the chat product a human asks questions in
  (Claude apps, ChatGPT apps). Consumes the retrieval worker or a
  Custom GPT; never maintains anything.
- **Model provider** — the API a resident service calls (Anthropic
  API, OpenAI API). Billed separately from any chat subscription; a
  ChatGPT or Claude subscription does not pay for a lore bot's API
  calls.

## Evidence states

Every product claim in this repo carries one of these, with a date:

- **verified** — a live test in an Eddic campaign, by a person or CI.
- **documented** — stated by the vendor's official docs; not yet
  exercised through Eddic.
- **unverified** — believed plausible; treat as a spike, not a path.
- **unsupported** — the vendor's own surface does not offer it.

A claim's state can only be promoted by new evidence, and evidence
goes stale: re-date on re-test. Nothing unverified may be a pattern
default (see `modules/CONTRACT.md`).

## Ledger

| claim | state | date | evidence |
|---|---|---|---|
| Claude app (phone), custom connector in normal chat: cold-context lore question triggers tools, ~10 s answer | verified | 2026-07-16 | owner live test on a real campaign absorption |
| Claude app, push-to-talk voice transcription into normal chat reaches connector tools | verified | 2026-07-16 | owner live test (same session) |
| Claude dedicated conversational voice mode reaches custom connectors | unsupported | 2026-07-16 | owner live test: mode self-reports no connector access |
| claude.ai web: custom connector add flow (Add ▾ → Add custom connector; URL-only auth) | verified | 2026-07-16 | driven live via browser; see retrieval PATTERN |
| Claude small-model chat tier uses worker tools and respects tier blindness | verified | 2026-07-16 | owner live test, player tier |
| ChatGPT web: custom MCP apps in developer mode | documented | 2026-07 | help.openai.com 12584461; web-only, plan-gated |
| ChatGPT full custom MCP: Business/Enterprise/Edu (Pro: read/fetch tools in developer mode) | documented | 2026-07 | help.openai.com 12584461 |
| ChatGPT Voice: apps/connectors | unsupported | 2026-07 | help.openai.com 11487775, 20001274 |
| ChatGPT mobile: Custom GPT Actions in text chat | documented | 2026-07 | help.openai.com 9442513 |
| ChatGPT Plus ($20/mo): retrieval via Custom GPT Actions (not custom MCP) | documented | 2026-07 | plan gating per official docs; Eddic route ships in the retrieval module |
| OpenAI API: separate billing from ChatGPT subscription; API data not used for training by default | documented | 2026-07 | help.openai.com 5722486 |
| Codex as maintaining agent (reads AGENTS.md natively) | documented | 2026-07 | AGENTS.md standard; not yet exercised on this repo |
| Claude Code as maintaining agent | verified | 2026-07-16 | built and maintains this repo; CLAUDE.md stub imports AGENTS.md |
| Companion conduct doctrine holds under adversarial asks (per client) | unverified | 2026-07-18 | rig: modules/companion/verify/conduct-acceptance.md; no live pass recorded |
| Anthropic API lore bot (corpus-in-cached-prompt) | verified | 2026-07-18 | live end-to-end on a real campaign: corpus answers, projection blindness, linked citations, self-refresh via fingerprint poll observed unprompted |
| OpenAI API lore bot (Responses adapter) | unverified | 2026-07-17 | request shape golden-tested in CI; no live deployment yet |
| Codex plugin format (.codex-plugin manifest + skills) | documented | 2026-07 | learn.chatgpt.com/docs/build-plugins; marketplace live since 2026-03 |
| Eddic installs as a Codex plugin (skill routes to AGENTS.md) | unverified | 2026-07-17 | shipped in-repo; needs one live `codex plugin install` + removal test |

## The cost story, provider-honest

The baseline build ("full Eddic on a $20/mo subscription alone")
holds for both vendors, by different routes: Claude's $20 tier takes
the custom-connector MCP route including phone dictation; ChatGPT's
$20 tier (Plus) takes the Custom GPT Actions route, text only, no
voice. Resident services (a lore bot) are API-billed extras on
either provider and never required.
