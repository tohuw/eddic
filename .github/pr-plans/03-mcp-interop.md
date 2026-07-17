# retrieval: harden MCP interoperability and read-only semantics

Tracking issue: #1

## Objective

Make the Worker rigorously cross-client while preserving Claude's capability-URL route.

## Planned files

- `modules/retrieval/templates/worker.js`
- `modules/retrieval/verify/harness.mjs`
- `modules/retrieval/verify/run.py`
- `modules/retrieval/PATTERN.md`
- `modules/retrieval/module.yaml`

## Scope

- Preserve capability-URL and bearer auth.
- Add read-only, non-destructive, closed-world tool annotations.
- Add canonical fetch and retain read_page alias.
- Add strict schemas, validation, and isError semantics.
- Return structured results plus portable text.
- Exercise cross-client Streamable HTTP request forms.
- Test tier isolation across all tools and result shapes.

## Acceptance criteria

- [ ] Claude connector remains compatible.
- [ ] Both auth styles pass.
- [ ] Player tier cannot infer DM pages.
- [ ] Tool scan exposes read-only semantics.
- [ ] Three-OS CI stays green.

## Non-goals

- No OAuth.
- No Apps SDK UI.
- No vector database.

## Implementation status

Implemented 2026-07-17. worker.js: read-only/closed-world annotations
on every tool; canonical `fetch` (id → structured document beside the
portable text) with read_page retained; argument validation returns
isError; unknown tools return isError; search carries
structuredContent results (id/title/url/snippet) while its verified
text shape is byte-identical to the live Claude path. Harness grew
from 12 to 27 checks: annotation scan, fetch tier walls (blind fetch
leaks neither text nor structured document), structured-result
emptiness for DM-only terms on the player tier, validation isError
cases, GET 405, and an event-stream-accepting client receiving JSON.
Capability-URL and bearer auth untouched. Module 0.2.0.
