# /// script
# requires-python = ">=3.9"
# ///
"""Verify the lore-bot module without discord/anthropic installed:
unit-test the pure helpers in botlib.py and compile-check bot.py."""

import os
import py_compile
import sys
import tempfile
import time
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
    # A page that still carries frontmatter with a DM-only key: the
    # corpus must strip it so the bot never serves a frontmatter secret.
    (proj / "characters" / "vault.md").write_text(
        "---\nvisibility: player\ndm_secret: the true name of the Warden\n"
        "---\n\n# The Vault\n\nwhat lies beneath\n", encoding="utf-8")
    corpus = botlib.corpus_from_dir(proj)
    checks.append(("=== characters/warden.md ===" in corpus,
                   "corpus heads pages with their paths"))
    checks.append(("keeper of the gate" in corpus, "corpus holds page text"))
    checks.append(("schema" not in corpus, "non-content excluded"))
    checks.append(("dm_secret" not in corpus and "true name" not in corpus,
                   "frontmatter stripped from the corpus (no DM key served)"))
    checks.append(("what lies beneath" in corpus,
                   "page body survives frontmatter stripping"))

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

    # --- what the table asked: the question log and the weekly digest ---
    day = 86400
    base = 1800000000                      # fixed epoch; no wall-clock deps
    lore = ("=== places/sunken-city.md ===\n# The Sunken City\n\n"
            "The Warden keeps the drowned gate.\n\n"
            "=== characters/warden.md ===\n# The Warden\n\n"
            "keeper of the gate")

    checks.append((botlib.utc_stamp(base) < botlib.utc_stamp(base + 1)
                   and botlib.utc_stamp(base).endswith("Z")
                   and len(botlib.utc_stamp(base)) == 20,
                   "stamps are fixed-width UTC and sort as strings"))

    terms = botlib.salient_terms("What about the Reavers and their oath?")
    checks.append((terms == ["reaver", "oath"],
                   "salient terms: filler dropped, plurals clustered"))
    checks.append((botlib.salient_terms("who is it") == [],
                   "short and common words carry no signal"))
    vocab = botlib.corpus_vocabulary(lore)
    checks.append(("sunken" in vocab and "warden" in vocab
                   and "oath" not in vocab,
                   "corpus vocabulary spans page paths and bodies"))

    known = botlib.page_paths(lore)
    checks.append((botlib.cited_paths(
        "See [The Warden](https://x.test/characters/warden).", known)
        == ["characters/warden.md"], "citations by link are counted"))
    checks.append((botlib.cited_paths(
        "The archive's page on the Sunken City says so.", known)
        == ["places/sunken-city.md"], "citations by page name are counted"))
    checks.append((botlib.cited_paths("The archive doesn't say.", known)
                   == [], "an uncited answer counts as uncited"))

    # the one identifier is one-way and salt-bound
    salt_file = tmp / "questions-salt.txt"
    salt = botlib.log_salt(salt_file)
    checks.append((botlib.log_salt(salt_file) == salt,
                   "the tag salt is created once and reused"))
    tag_a = botlib.asker_tag(4815162342, salt)
    tag_b = botlib.asker_tag(1234567890, salt)
    checks.append((tag_a != tag_b
                   and tag_a == botlib.asker_tag(4815162342, salt)
                   and tag_a != botlib.asker_tag(4815162342, "other-salt")
                   and "4815162342" not in tag_a,
                   "asker tags are stable, distinct, salt-bound, one-way"))

    log = tmp / "questions.jsonl"
    for age_days, q, cited, who in [
            (20, "who was the first Warden?", ["characters/warden.md"], tag_a),
            (9, "what is the Warden's oath?", [], tag_a),
            (9, "where do the reavers camp?", [], tag_b),
            (3, "who is the Warden?", ["characters/warden.md"], tag_a),
            (2, "what is the Warden's oath?", [], tag_b),
            (1, "is the oath binding on the reavers?", [], tag_b)]:
        when = base - age_days * day
        botlib.log_question(
            log, botlib.question_record(
                q, cited=cited, outcome="answered" if cited else "uncited",
                who=who, when=when),
            keep_days=14, when=base)
    rows = botlib.read_questions(log)
    checks.append((len(rows) == 5 and all("first Warden" not in r["q"]
                                          for r in rows),
                   "retention drops rows past the keep window on write"))
    raw = log.read_text(encoding="utf-8")
    checks.append(("4815162342" not in raw and "1234567890" not in raw,
                   "no account id is ever written to the log"))
    checks.append((set(rows[0]) == {"at", "q", "cited", "outcome", "who"},
                   "a row holds only time, question, pages, outcome, tag"))

    d = botlib.weekly_digest(rows, lore, when=base, days=7)
    checks.append((d["asked"] == 3 and d["prior_asked"] == 2,
                   "the digest windows this week against last week"))
    checks.append(([t["term"] for t in d["themes"]] == ["oath", "warden"]
                   and d["themes"][0]["count"] == 2
                   and d["themes"][0]["examples"][0].startswith("what is"),
                   "recurring themes are counted, not guessed"))
    gaps = {g["term"] for g in d["gaps"]}
    checks.append(("oath" in gaps and "reaver" in gaps
                   and "warden" not in gaps,
                   "the gap list names subjects the wiki has no page for"))
    checks.append((len(d["poor"]) == 2
                   and all("oath" in p["q"] or "reaver" in p["q"]
                           for p in d["poor"]),
                   "questions answered badly or not at all are listed"))
    checks.append(([p["path"] for p in d["pages"]]
                   == ["characters/warden.md"],
                   "pages the table actually reached are ranked"))
    checks.append((d["new_topics"] == [],
                   "nothing counts as new when last week asked it too"))
    fresh = botlib.weekly_digest(
        [botlib.question_record("what do the reavers want?", who=tag_a,
                                outcome="uncited", when=base - day),
         botlib.question_record("who leads the reavers?", who=tag_b,
                                outcome="uncited", when=base - 2 * day),
         botlib.question_record("who is the Warden?", who=tag_a,
                                cited=["characters/warden.md"],
                                when=base - 10 * day)],
        lore, when=base, days=7)
    checks.append(([t["term"] for t in fresh["new_topics"]] == ["reaver"],
                   "newly popular means popular now and absent before"))

    text = botlib.render_digest(d)
    checks.append(("oath" in text and "asked this week" in text
                   and tag_a not in text and tag_b not in text,
                   "the rendered digest shows subjects, never who asked"))
    checks.append(("Nobody asked" in botlib.render_digest(
        botlib.weekly_digest([], lore, when=base)),
        "a quiet week renders as a quiet week"))

    # forget me: the rows go, and the tag joins the never-record list
    optout = tmp / "questions-optout.txt"
    gone = botlib.forget_asker(log, tag_b)
    left = botlib.read_questions(log)
    checks.append((gone == 3 and all(r["who"] != tag_b for r in left)
                   and any(r["who"] == tag_a for r in left),
                   "forget me erases one player's rows and no one else's"))
    checks.append((botlib.set_optout(optout, tag_b) is True
                   and botlib.read_optouts(optout) == {tag_b}
                   and botlib.set_optout(optout, tag_b) is False,
                   "the never-record list holds tags, and adding is idempotent"))
    checks.append((botlib.set_optout(optout, tag_b, False) is True
                   and botlib.read_optouts(optout) == set(),
                   "opting back in is one step and leaves no name behind"))

    monday = base - (time.localtime(base).tm_wday * day)
    hour = time.localtime(monday).tm_hour
    checks.append((botlib.digest_due("", 0, hour, when=monday)
                   and not botlib.digest_due(
                       time.strftime("%Y-%m-%d", time.localtime(monday)),
                       0, hour, when=monday),
                   "the digest is owed once on its day, not twice"))
    checks.append((not botlib.digest_due("", (time.localtime(monday).tm_wday
                                              + 1) % 7, hour, when=monday),
                   "no digest on any other day"))
    checks.append((not botlib.digest_due("", 0, 23, when=monday)
                   if hour < 23 else True,
                   "no digest before its hour"))

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
