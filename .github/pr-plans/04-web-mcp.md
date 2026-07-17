# retrieval: add a verified ChatGPT web MCP application path

Tracking issue: #1

## Objective

Replace speculative ChatGPT prose with a plan-aware, bearer-authenticated route verified on ChatGPT web.

## Planned files

- `modules/retrieval/PATTERN.md`
- `docs/compatibility.md`
- `modules/retrieval/verify/chatgpt-acceptance.md`

## Scope

- Use bearer app auth instead of a URL token.
- Document Pro and managed-workspace setup separately.
- Provide click-through and consented agent-driven routes.
- State web, agent-mode, mobile, and voice limits accurately.
- Mirror the successful Claude cold-context test.
- Record plan, date, selection behavior, isolation, and latency.

## Acceptance criteria

- [ ] Cold ChatGPT context retrieves a wiki-only term automatically
      (generalized per AGENTS.md: no campaign-specific examples in docs).
- [ ] Player app cannot discover DM-only lore.
- [ ] Token stays out of endpoint URL.
- [ ] Status becomes verified only after live test.

## Non-goals

- No mobile or voice MCP claim.
- No Claude setup change.

## Implementation status

Implemented 2026-07-17 as documentation plus a live-test rig; the
route itself remains UNVERIFIED by design. retrieval PATTERN's
ChatGPT section now separates plan scopes (Pro developer-mode vs
managed workspace), states web-only/no-mobile/no-Voice plainly,
prefers bearer app auth with capability URL as fallback, and offers
click-through and consented agent-driven routes.
verify/chatgpt-acceptance.md is the fill-in acceptance record that
mirrors the Claude cold-context test (cold context, consumer-side
tier isolation, tool scan, surface limits); passing it is the only
way the ledger and module.yaml chatgpt rows get promoted to
verified. Compatibility ledger rows were seeded in #2.
