# contract: make provider claims testable and evidence-backed

Tracking issue: #1

## Objective

Extend the module contract and CI floor so provider-neutral claims require explicit compatibility metadata and evidence.

## Planned files

- `modules/CONTRACT.md`
- `tools/floor.py`
- `modules/*/module.yaml`
- `docs/compatibility.md`

## Scope

- Add compatibility metadata for maintaining agents, answer clients, and providers.
- Require verified claims to point to automated or dated manual evidence.
- Keep unverified paths out of defaults.
- Reject provider names in prose absent from compatibility metadata.
- Populate truthful metadata for all current modules.

## Acceptance criteria

- [ ] CI fails on unsupported provider-neutral claims.
- [ ] All module verifies stay green on three OSes.
- [ ] Provider-exclusive modules state a fallback.
- [ ] No live credentials enter fixtures.

## Non-goals

- No provider implementation.

## Implementation status

Planning draft only. Replace this section with implementation and verification evidence before ready-for-review.
