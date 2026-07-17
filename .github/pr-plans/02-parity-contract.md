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

Implemented 2026-07-17. floor.py parses a flat `compatibility:` block
in module.yaml and fails when a PATTERN mentions a vendor without an
entry, when a status is not one of the four evidence states, when an
entry is undated, or when `verified` cites no evidence. CONTRACT.md
records the rule in the deterministic-floor list. Truthful metadata
populated for the three modules that name vendors today: wiki
(claude, verified — the stub convention), retrieval (claude verified
2026-07-16 live tests; chatgpt documented, connect flow UNVERIFIED),
lore-bot (anthropic verified — production-proven design, CI-verified
core). Checked live: the floor failed on all three before the
metadata landed and passes after. No fixtures carry credentials.
