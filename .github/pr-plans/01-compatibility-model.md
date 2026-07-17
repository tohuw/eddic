# docs: define runtime, answer-client, and API-provider compatibility

Tracking issue: #1

## Objective

Define Eddic's provider/surface model, establish a dated compatibility ledger, and correct claims that conflate Codex, ChatGPT, OpenAI API, Claude, and Anthropic.

## Planned files

- `DESIGN.md`
- `README.md`
- `ROADMAP.md`
- `docs/compatibility.md`

## Scope

- Define maintaining agent, answer client, and model provider separately.
- Add verified, documented, unverified, and unsupported evidence states.
- Record Claude cold-context and voice retrieval as verified.
- Record ChatGPT web, mobile, voice, and plan constraints from official docs.
- Correct subscription retrieval versus separately billed resident API services.
- Keep AGENTS.md canonical and retain the CLAUDE.md stub.

## Acceptance criteria

- [ ] No runtime behavior changes.
- [ ] No Claude capability is downgraded.
- [ ] Every product claim has a date and evidence state.
- [ ] ChatGPT voice is documented as unsupported upstream.

## Non-goals

- No connector implementation.
- No OpenAI API integration.

## Implementation status

Implemented 2026-07-17. `docs/compatibility.md` carries the role
definitions, the four evidence states, the dated ledger (Claude
verified rows from the 2026-07-16 live tests; ChatGPT rows documented
from official help-center articles; ChatGPT Voice recorded
unsupported), and the provider-honest cost story. DESIGN.md gained the
three-role vocabulary entry and the baseline-build principle now
points at the ledger instead of implying route parity. No runtime
changes; no Claude capability touched.
