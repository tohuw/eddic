# lore-bot: add an OpenAI Responses provider without changing Anthropic defaults

Tracking issue: #1

## Objective

Add a provider interface and OpenAI Responses adapter while golden-testing existing Anthropic behavior.

## Planned files

- `modules/lore-bot/templates/bot.py`
- `modules/lore-bot/templates/providers/*`
- `modules/lore-bot/templates/variables-example.txt`
- `modules/lore-bot/PATTERN.md`
- `modules/lore-bot/module.yaml`
- `modules/lore-bot/verify/run.py`

## Scope

- Define a portable answer provider interface.
- Move current Anthropic request shape into an unchanged adapter.
- Add OpenAI Responses with store=false.
- Order stable corpus/persona before volatile input for caching.
- Use a stable prompt_cache_key from campaign and corpus fingerprint.
- Add provider-specific keys and models.
- Retain legacy MODEL for one release.
- Correct the false easy-swap claim.

## Acceptance criteria

- [ ] Anthropic golden request passes.
- [ ] OpenAI request, cache, extraction, refusal, and error tests use fakes.
- [ ] CI needs no network or keys.
- [ ] Anthropic remains default.
- [ ] API billing is separate from subscriptions.

## Non-goals

- No model router.
- No live keys in CI.
- No firewall change.

## Implementation status

Planning draft only. Replace this section with implementation and verification evidence before ready-for-review.
