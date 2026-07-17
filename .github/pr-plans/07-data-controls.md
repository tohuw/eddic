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

Implemented 2026-07-17. docs/data-controls.md: dated privacy profiles
for both vendors (consumer switches incl. ChatGPT Temporary Chat ~30d
retention and thumbs-feedback sharing; API no-training defaults),
what-content-reaches-whom, and token-handling doctrine (bearer
preferred where the UI allows, capability URL where Claude needs it;
fingerprints for reference; exposure means rotation). floor.py secret
scan now catches sk-proj- and long legacy sk- OpenAI keys — length
floors keep prose placeholders from false-firing (self-tested).
retrieval PATTERN prefers direct configuration over printing tokens;
DESIGN's rights section and lore-bot's roster line link the profile.
No keychain framework: rotation stayed a one-sentence operation, so
none was needed. Claude capability URLs untouched.