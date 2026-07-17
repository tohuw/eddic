"""OpenAI Responses adapter. No explicit cache markers: OpenAI's
prompt caching is automatic on long stable prefixes, so the corpus
leads the instructions and must stay byte-stable between calls; the
roster and question follow it."""

import openai


class OpenAIProvider:
    def __init__(self):
        self.client = openai.OpenAI()

    def complete(self, *, model, max_tokens, corpus_text, persona,
                 roster, prompt):
        instructions = f"{corpus_text}\n\n{persona}"
        if roster:
            instructions += f"\n\nTABLE ROSTER (private):\n{roster}"
        res = self.client.responses.create(
            model=model, max_output_tokens=max_tokens,
            instructions=instructions, input=prompt)
        return res.output_text
