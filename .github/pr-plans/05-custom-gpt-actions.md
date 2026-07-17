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

Implemented 2026-07-17. worker.js grew a read-only REST facade
(/api/pages, /api/page?id=, /api/search?q=) sharing the MCP tools'
search logic, tier walls, and 404-parity for hidden pages; non-GET is
405. templates/openapi.json carries the three actions (listPages,
readPage, searchWiki) with bearer security; instruction templates for
player and DM GPTs are voice-neutral per DESIGN principle 11 with
persona explicitly the owner's add-on. PATTERN documents the
per-tier-GPT rule, bearer keys out of URLs, and no-Voice limit.
Harness: 8 new REST checks (auth, tier counts via capability path,
DM-page 404 for player, search blindness, GET-only); run.py validates
the OpenAPI actions. Live web+mobile use remains UNVERIFIED pending
verify/chatgpt-acceptance.md. Module 0.3.0.
