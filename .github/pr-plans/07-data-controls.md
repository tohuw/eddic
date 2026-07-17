# security: add provider data-control profiles and safer token handling

Tracking issue: #1

## Objective

Operationalize provider privacy guidance and safer secret handling without removing Claude capability URLs.

## Planned files

- `DESIGN.md`
- `docs/data-controls.md`
- `tools/floor.py`
- `modules/retrieval/PATTERN.md`
- `modules/retrieval/scripts/*`
- `modules/lore-bot/PATTERN.md`

## Scope

- Document consumer opt-outs and API default no-training posture.
- Document feedback, Temporary Chat, Memory/apps, Voice, and retention caveats.
- Detect current OpenAI key formats.
- Prefer bearer auth for ChatGPT and capability URL where Claude needs it.
- Add redacted fingerprints and deterministic rotation.
- Avoid printing tokens when direct setup is available.
- Rotate after transcript, screenshot, or log exposure.

## Acceptance criteria

- [ ] Profiles are dated and linked from DESIGN.md.
- [ ] Secret fixtures catch both providers without placeholder false positives.
- [ ] Rotation is a one-sentence operation.
- [ ] Claude capability URLs still work.

## Non-goals

- No zero-retention claim.
- No keychain framework unless proven needed.

## Implementation status

Planning draft only. Replace this section with implementation and verification evidence before ready-for-review.
