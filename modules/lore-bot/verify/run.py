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

    # bot.py compiles (deps not required to parse)
    try:
        py_compile.compile(str(TEMPLATES / "bot.py"), doraise=True)
        checks.append((True, "bot.py compiles"))
    except py_compile.PyCompileError as e:
        checks.append((False, f"bot.py compile error: {e}"))

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print("verify ok: lore-bot module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
