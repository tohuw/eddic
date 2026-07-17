"""Answer providers for the lore bot.

One duck-typed interface: provider.complete(model=, max_tokens=,
corpus_text=, persona=, roster=, prompt=) -> str. Each adapter owns
its provider's request shape — including its caching strategy, which
is the part that genuinely differs: Anthropic wants an explicit
cache_control breakpoint after the corpus block; OpenAI caches long
stable prefixes automatically, so the corpus just goes first and
stays byte-stable. The roster always rides behind the cached region
so private names never enter a shared cache prefix's reuse story.

Anthropic is the default (production-proven). Imports are lazy so a
deployment only needs its own provider's package installed.
"""

DEFAULT_MODELS = {"anthropic": "claude-sonnet-5", "openai": "gpt-5"}


def get_provider(name):
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider()
    raise ValueError(f"unknown PROVIDER: {name} (anthropic | openai)")
