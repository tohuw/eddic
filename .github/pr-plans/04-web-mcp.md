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

- [ ] Cold ChatGPT context retrieves Stones of Saudient automatically.
- [ ] Player app cannot discover DM-only lore.
- [ ] Token stays out of endpoint URL.
- [ ] Status becomes verified only after live test.

## Non-goals

- No mobile or voice MCP claim.
- No Claude setup change.

## Implementation status

Planning draft only. Replace this section with implementation and verification evidence before ready-for-review.
