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

Planning draft only. Replace this section with implementation and verification evidence before ready-for-review.
