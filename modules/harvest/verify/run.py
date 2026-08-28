# /// script
# requires-python = ">=3.9"
# ///
"""Verify the harvest module against a fake Discord, so the checks run
offline and prove the properties the table was promised: watermarks
advance, no message text is ever persisted, opted-out authors vanish,
only the DM's words become canon candidates, and a failing channel
neither loses its place nor takes the run down with it."""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "harvest.py"
spec = importlib.util.spec_from_file_location("harvest", SCRIPT)
harvest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harvest)

DM, PLAYER, LURKER, BOT = "11", "22", "33", "44"
FAILING = "999"

RULING = ("Ruling for next session: a Rider native to its own level "
          "keeps the bigger die, so Phoenix Talon stays 3d10 and an "
          "upcast Bog Bile does not catch up to it.")


def msg(mid, author, text, name="someone", bot=False):
    return {"id": str(mid), "timestamp": f"2026-08-27T00:00:{int(mid):02d}Z",
            "author": {"id": author, "username": name, "bot": bot},
            "content": text}


PAGES = {
    "100": [
        msg(1, PLAYER, "Is Tyre's library still standing? Anyone know?"),
        msg(2, DM, RULING),
        msg(3, LURKER, "I would rather not be quoted anywhere, thanks."),
        msg(4, BOT, "The archive doesn't say.", name="Snorri", bot=True),
        msg(5, PLAYER, "What is a Mosswife exactly?"),
    ],
    "200": [msg(6, DM, "short")],
}


def transport(url, token):
    if f"/channels/{FAILING}/" in url:
        raise RuntimeError("403 forbidden (bot cannot read this channel)")
    chan = url.split("/channels/")[1].split("/")[0]
    page = PAGES.get(chan, [])
    if "after=" in url:
        after = int(url.split("after=")[1].split("&")[0])
        page = [m for m in page if int(m["id"]) > after]
    elif "before=" in url:
        before = int(url.split("before=")[1].split("&")[0])
        page = [m for m in page if int(m["id"]) < before]
    return list(reversed(page))          # Discord returns newest-first


def check(label, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {label}" + (f" — {detail}" if detail and not ok else ""))
    return 0 if ok else 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-harvest-verify-"))
    corpus = tmp / "corpus"
    corpus.mkdir()
    (corpus / "tyre.md").write_text("# Tyre\nThe library of Tyre.\n",
                                    encoding="utf-8")
    state = tmp / "harvest-state.json"
    config = {
        "announced": True,
        "channels": {"100": "rules-questions", "200": "general",
                     FAILING: "locked-room"},
        "dm_ids": [DM], "bot_ids": [BOT], "optout_ids": [LURKER],
        "corpus_dir": str(corpus),
        "state_file": str(state),
    }

    fails = 0

    # The consent gate comes before anything reaches the network.
    unarmed = dict(config)
    unarmed.pop("announced", None)
    packet0, code0 = harvest.do_pull(unarmed, state, "token", transport, 5)
    fails += check("an unannounced campaign refuses to pull at all",
                   packet0 is None and code0 == 2)
    fails += check("and wrote no state doing it", not state.exists())

    packet, code = harvest.do_pull(config, state, "token", transport, 5)
    fails += check("pull exits 0 with a packet", code == 0 and packet)

    texts = json.dumps(packet)
    fails += check("opted-out author is absent from the packet",
                   "rather not be quoted" not in texts)
    fails += check("the DM's ruling is a canon candidate",
                   any("Phoenix Talon" in r["text"]
                       for r in packet["dm_statements"]))
    fails += check("a player's assertion is not a canon candidate",
                   all(r["who"] == "dm" for r in packet["dm_statements"]))
    fails += check("short DM chatter is not promoted to a ruling",
                   all(len(r["text"]) >= harvest.MIN_RULING_CHARS
                       for r in packet["dm_statements"]))
    fails += check("player questions are collected",
                   len(packet["player_questions"]) == 2)
    fails += check("a proper noun the wiki lacks is reported",
                   "Mosswife" in packet["novel_proper_nouns"])
    fails += check("a proper noun the wiki already has is not",
                   "Tyre" not in packet["novel_proper_nouns"])
    fails += check("the unreadable channel is reported, not fatal",
                   any("locked-room" in f
                       for f in packet["window"]["failed_channels"]))

    saved = json.loads(state.read_text(encoding="utf-8"))
    fails += check("watermark advanced for a channel that returned messages",
                   saved["watermarks"].get("100") == "5")
    fails += check("watermark withheld for the failing channel",
                   FAILING not in saved["watermarks"])
    blob = json.dumps(saved)
    fails += check("state holds no message text",
                   "Phoenix Talon" not in blob and "Mosswife" not in blob)

    packet2, _ = harvest.do_pull(config, state, "token", transport, 5)
    fails += check("second run is empty — the watermark held",
                   packet2["counts"]["messages"] == 0)
    fails += check("the first run read history, it did not start blank",
                   any("rules-questions" in b
                       for b in packet["window"]["backfilled_channels"]))

    # A bot without the Message Content intent gets messages with the
    # words removed. That must refuse loudly and hold its place, or the
    # watermark sails past a window nobody could read.
    wordless = {"777": [{"id": "9", "timestamp": "2026-08-27T00:00:09Z",
                         "author": {"id": PLAYER, "username": "someone"},
                         "content": ""} for _ in range(3)]}
    PAGES.update(wordless)
    state2 = tmp / "state-intent.json"
    cfg2 = dict(config, channels={"777": "muted-by-intent"},
                state_file=str(state2))
    packet3, _ = harvest.do_pull(cfg2, state2, "token", transport, 5)
    fails += check("wordless channel is reported as a missing intent",
                   any("Message Content" in f
                       for f in packet3["window"]["failed_channels"]))
    saved2 = json.loads(state2.read_text(encoding="utf-8"))
    fails += check("and its watermark is held, not advanced",
                   "777" not in saved2["watermarks"])

    good = {"findings": [{"category": "gap", "severity": "info",
                          "summary": "s", "evidence": "e", "suggestion": "x"}]}
    bad = {"findings": [{"category": "vibes", "severity": "info",
                         "summary": "", "evidence": "e", "suggestion": "x"}]}
    fails += check("a well-formed finding validates",
                   harvest.validate_findings(good) == [])
    errs = harvest.validate_findings(bad)
    fails += check("a bad category and an empty summary are both caught",
                   len(errs) == 2, str(errs))

    big = {"kind": "x", "player_questions": [
        {"text": "q" * 400, "at": str(i)} for i in range(500)],
        "dm_statements": []}
    packed = harvest.compress(dict(big))
    fails += check("an oversized packet is compressed",
                   len(json.dumps(packed)) <= harvest.PACKET_CHAR_BUDGET)
    fails += check("and says so out loud",
                   bool(packed.get("compression_notes")))

    # ---- the capability: the nightly runner, in the bot's process ----
    capspec = importlib.util.spec_from_file_location(
        "harvest_capability",
        Path(__file__).resolve().parent.parent / "templates"
        / "harvest_capability.py")
    cap_mod = importlib.util.module_from_spec(capspec)
    capspec.loader.exec_module(cap_mod)

    class FakeClient:
        class _Loop:
            def create_task(self, coro):
                coro.close()
        loop = _Loop()

    cap = cap_mod.setup(FakeClient())
    packet = {"counts": {"messages": 3}, "checklist": [], "window": {},
              "findings_schema": {}}

    class GoodLLM:
        def complete(self, **kw):
            self.kw = kw
            return ('here you go\n{"findings": [{"category": "gap", '
                    '"severity": "info", "summary": "s", "evidence": "e", '
                    '"suggestion": "x"}]}')

    llm = GoodLLM()
    found = cap.mine(packet, llm, "model", 500)
    fails += check("capability mines findings out of a chatty reply",
                   len(found) == 1 and found[0]["category"] == "gap")
    fails += check("the packet rides in the cached corpus slot",
                   "HARVEST PACKET" in llm.kw["corpus_text"])
    fails += check("and no roster is ever handed to the harvest pass",
                   llm.kw["roster"] == "")

    class BadLLM:
        def complete(self, **kw):
            return '{"findings": [{"category": "vibes"}]}'

    try:
        cap.mine(packet, BadLLM(), "model", 500)
        fails += check("a malformed finding is refused, not filed", False)
    except RuntimeError:
        fails += check("a malformed finding is refused, not filed", True)

    print("verify ok: harvest module" if not fails
          else f"verify FAILED: harvest module ({fails})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
