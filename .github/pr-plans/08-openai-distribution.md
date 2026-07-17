# distribution: add an optional Codex/ChatGPT plugin and app template

Tracking issue: #1

## Objective

Package Eddic for OpenAI discovery while keeping AGENTS.md, patterns, and CLI canonical.

## Planned files

- `.codex-plugin/plugin.json`
- `skills/*`
- `apps/*`
- `docs/compatibility.md`
- `README.md`

## Scope

- Add an optional Codex skill routing to current modules.
- Add an app template for an existing Worker.
- Reference canonical patterns instead of copying them.
- Expose compatibility and setup requirements in metadata.
- Verify clean install and removal.

## Acceptance criteria

- [ ] Eddic works without the plugin.
- [ ] Plugin defers to AGENTS.md and PATTERN.md.
- [ ] Claude setup is unchanged.
- [ ] Plugin shortens adoption instead of creating another architecture.

## Non-goals

- No Apps SDK UI without need.
- No provider fork.
- No marketplace submission.

## Implementation status

Implemented 2026-07-17 against the real plugin spec
(learn.chatgpt.com/docs/build-plugins, verified live — the format
launched with the Codex marketplace 2026-03; initial skepticism
withdrawn). The repo root is the plugin: .codex-plugin/plugin.json
(name/version/description/skills only) plus skills/eddic/SKILL.md, a
thin router to AGENTS.md and modules/README.md that duplicates
nothing — Eddic works identically without it, satisfying both
acceptance gates by construction. Deliberately NOT shipped: an
.app.json (its plugin_asdk_app ID is minted per-user in dev-mode
ChatGPT — a live acceptance step, not a truthful template) and any
bundled mcpServers entry (the worker URL is per-campaign). Ledger
rows added: plugin format documented; the install itself unverified
until one live `codex plugin install tohuw/eddic` + removal test.