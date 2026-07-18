"""Anthropic Messages adapter — the original, production-proven shape:
corpus in an ephemeral-cached system block, persona after the cache
breakpoint, roster last (private, never cached with the corpus)."""

import anthropic


class AnthropicProvider:
    def __init__(self):
        self.client = anthropic.Anthropic()

    def complete(self, *, model, max_tokens, corpus_text, persona,
                 roster, prompt):
        blocks = [{"type": "text", "text": corpus_text,
                   "cache_control": {"type": "ephemeral"}},
                  {"type": "text", "text": persona}]
        if roster:
            blocks.append({"type": "text",
                           "text": f"TABLE ROSTER (private):\n{roster}"})
        res = self.client.messages.create(
            model=model, max_tokens=max_tokens, system=blocks,
            # thinking off: it spends the token budget and the table's
            # patience; a lore answer needs recall, not deliberation
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}])
        # content may lead with thinking blocks; answer = the text block
        return next(b.text for b in res.content
                    if getattr(b, "type", "") == "text")
