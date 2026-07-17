# retrieval: add Custom GPT Actions for Plus and mobile text

Tracking issue: #1

## Objective

Add REST/OpenAPI and generated Custom GPT artifacts for web and mobile text retrieval when custom MCP is unavailable.

## Planned files

- `modules/retrieval/templates/worker.js`
- `modules/retrieval/templates/openapi.json`
- `modules/retrieval/templates/chatgpt-dm-instructions.md`
- `modules/retrieval/templates/chatgpt-player-instructions.md`
- `modules/retrieval/PATTERN.md`
- `modules/retrieval/verify/*`

## Scope

- Expose read-only list, fetch, and search REST endpoints.
- Generate an OpenAPI schema for GPT Actions.
- Use bearer keys with distinct DM and player GPTs.
- Ship corpus-only instructions, citations, starters, and not-found behavior.
- Verify web creation and mobile use.
- State that Actions do not run in Voice.

## Acceptance criteria

- [ ] Schema validates and finds three actions.
- [ ] Web and mobile text retrieve canon.
- [ ] Player GPT stays blind to DM lore.
- [ ] No endpoint writes state.
- [ ] Existing MCP and Claude tests stay green.

## Non-goals

- No GPT Store publication.
- No voice claim.

## Implementation status

Planning draft only. Replace this section with implementation and verification evidence before ready-for-review.
