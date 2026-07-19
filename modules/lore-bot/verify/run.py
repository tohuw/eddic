# /// script
# requires-python = ">=3.9"
# ///
"""Verify the lore-bot module without discord/anthropic installed:
unit-test the pure helpers in botlib.py and compile-check bot.py."""

import os
import py_compile
import sys
import tempfile
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
sys.path.insert(0, str(TEMPLATES))
import botlib  # noqa: E402


def main():
    checks = []
    tmp = Path(tempfile.mkdtemp(prefix="eddic-lorebot-verify-"))

    # config precedence: real env beats the file
    var = tmp / "variables.txt"
    var.write_text("LOREBOT_A=from-file\nLOREBOT_B=from-file\n# comment\n",
                   encoding="utf-8")
    os.environ["LOREBOT_A"] = "from-env"
    botlib.load_variables(var)
    checks.append((os.environ["LOREBOT_A"] == "from-env",
                   "env overrides variables.txt"))
    checks.append((os.environ["LOREBOT_B"] == "from-file",
                   "file fills unset variables"))

    # corpus build + non-content exclusion
    proj = tmp / "player"
    (proj / "characters").mkdir(parents=True)
    (proj / "index.md").write_text("# Realm\n\ncatalog\n", encoding="utf-8")
    (proj / "characters" / "warden.md").write_text(
        "# The Warden\n\nkeeper of the gate\n", encoding="utf-8")
    (proj / "AGENTS.md").write_text("# schema\n", encoding="utf-8")
    corpus = botlib.corpus_from_dir(proj)
    checks.append(("=== characters/warden.md ===" in corpus,
                   "corpus heads pages with their paths"))
    checks.append(("keeper of the gate" in corpus, "corpus holds page text"))
    checks.append(("schema" not in corpus, "non-content excluded"))

    # fingerprint change detection
    fp1 = botlib.dir_fingerprint(proj)
    (proj / "characters" / "warden.md").write_text(
        "# The Warden\n\nkeeper of the gate, and of the oath\n",
        encoding="utf-8")
    fp2 = botlib.dir_fingerprint(proj)
    checks.append((fp1 != fp2, "fingerprint moves when a page changes"))
    checks.append((fp2 == botlib.dir_fingerprint(proj),
                   "fingerprint stable when nothing changes"))

    # message splitting
    long = "\n".join(f"line {i} " + "x" * 80 for i in range(60))
    chunks = botlib.split_message(long, limit=2000)
    checks.append((all(len(c) <= 2000 for c in chunks),
                   "chunks under the Discord limit"))
    checks.append(("".join(chunks).replace("\n", "") ==
                   long.replace("\n", ""), "no text lost in splitting"))
    checks.append((botlib.split_message("short") == ["short"],
                   "short messages pass through"))

    # mention stripping
    checks.append((botlib.strip_bot_mention("<@12345> who is the warden?",
                                            12345) == "who is the warden?",
                   "mention stripped"))

    # corpus page helpers (convene builds on these)
    corpus = ("=== places/warden.md ===\n# The Warden\n\ntext\n\n"
              "=== campaigns/c/sessions/session-1.md ===\n"
              "# Session 1 — Arrival\n\nrecap")
    checks.append((botlib.page_paths(corpus)
                   == ["places/warden.md",
                       "campaigns/c/sessions/session-1.md"],
                   "page_paths lists every page header"))
    checks.append((botlib.new_session_pages(corpus, set())
                   == ["campaigns/c/sessions/session-1.md"],
                   "new_session_pages finds unannounced recaps only"))
    checks.append((botlib.page_title(
        corpus, "campaigns/c/sessions/session-1.md")
        == "Session 1 — Arrival", "page_title reads the H1"))

    # bot.py and providers compile (deps not required to parse)
    for src in [TEMPLATES / "bot.py",
                *sorted((TEMPLATES / "providers").glob("*.py"))]:
        try:
            py_compile.compile(str(src), doraise=True)
            checks.append((True, f"{src.name} compiles"))
        except py_compile.PyCompileError as e:
            checks.append((False, f"{src.name} compile error: {e}"))

    # golden tests: pin each provider's request shape with fake SDKs,
    # so a refactor cannot silently change what the APIs receive
    import types

    captured = {}

    fake_anthropic = types.ModuleType("anthropic")

    class _FakeAnthropicClient:
        class messages:
            @staticmethod
            def create(**kw):
                captured["anthropic"] = kw
                # thinking block first, like modern models actually
                # answer — the adapter must pick the text block
                return types.SimpleNamespace(content=[
                    types.SimpleNamespace(type="thinking"),
                    types.SimpleNamespace(type="text", text="ok")])
    fake_anthropic.Anthropic = _FakeAnthropicClient
    sys.modules["anthropic"] = fake_anthropic

    fake_openai = types.ModuleType("openai")

    class _FakeOpenAIClient:
        class responses:
            @staticmethod
            def create(**kw):
                captured["openai"] = kw
                return types.SimpleNamespace(output_text="ok")
    fake_openai.OpenAI = _FakeOpenAIClient
    sys.modules["openai"] = fake_openai

    import providers
    kwargs = dict(model="m", max_tokens=7, corpus_text="CORPUS",
                  persona="PERSONA", roster="ROSTER", prompt="Q")

    out = providers.get_provider("anthropic").complete(**kwargs)
    a = captured["anthropic"]
    sysb = a["system"]
    checks.append((out == "ok" and a["model"] == "m"
                   and a["max_tokens"] == 7,
                   "anthropic: model/max_tokens pass through"))
    checks.append((sysb[0]["text"] == "CORPUS" and
                   sysb[0].get("cache_control") == {"type": "ephemeral"},
                   "anthropic: corpus is the cached system block"))
    checks.append((sysb[1]["text"] == "PERSONA" and
                   "cache_control" not in sysb[1],
                   "anthropic: persona after the cache breakpoint"))
    checks.append((len(sysb) == 3 and "ROSTER" in sysb[2]["text"],
                   "anthropic: roster last, behind the breakpoint"))
    checks.append((a["messages"] == [{"role": "user", "content": "Q"}],
                   "anthropic: prompt is the user message"))
    checks.append((a.get("thinking") == {"type": "disabled"},
                   "anthropic: thinking disabled (budget and latency)"))

    out = providers.get_provider("openai").complete(**kwargs)
    o = captured["openai"]
    checks.append((out == "ok" and o["model"] == "m"
                   and o["max_output_tokens"] == 7,
                   "openai: model/max_output_tokens pass through"))
    checks.append((o["instructions"].startswith("CORPUS"),
                   "openai: corpus leads the stable cacheable prefix"))
    checks.append((o["instructions"].rfind("ROSTER") >
                   o["instructions"].rfind("PERSONA"),
                   "openai: roster rides behind persona, never in front"))
    checks.append((o["input"] == "Q", "openai: prompt is the input"))

    no_roster = dict(kwargs, roster="")
    providers.get_provider("anthropic").complete(**no_roster)
    checks.append((len(captured["anthropic"]["system"]) == 2,
                   "anthropic: no roster block when roster empty"))
    try:
        providers.get_provider("gemini")
        checks.append((False, "unknown provider rejected"))
    except ValueError:
        checks.append((True, "unknown provider rejected"))

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print("verify ok: lore-bot module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
