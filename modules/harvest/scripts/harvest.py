# /// script
# requires-python = ">=3.9"
# ///
"""eddic harvest — pull what the table said in Discord since last night
and assemble a packet the maintaining agent can mine for the wiki.

Usage:
    uv run harvest.py --pull [--config FILE] [--state FILE] [--out FILE]
                      [--max-pages N] [--token TOKEN]
        Pull new messages from allow-listed channels, advance the
        watermarks, and write the harvest packet (JSON) to --out or
        stdout.
    uv run harvest.py --validate [FILE]
        Validate a findings document (FILE or stdin) against the finding
        schema. Exit 0 all valid, 1 violations, 2 usage.
    (bare, as a vendored eddic verb: config and state paths come from
     EDDIC_CONFIG.)

Discord is already the log. This verb keeps no message store of its own:
it remembers one message id per channel — a watermark — and asks Discord
for what came after. The state file therefore holds ids and timestamps
and never a word of what anyone said, which is the honest version of the
promise the table is given. Deleted messages are gone, as they should be.

The one thing that is NOT recoverable this way is what the lore bot was
asked and whether it could answer; that lives in the bot's own question
log (lore-bot module) and is read here, not re-collected.

Everything this produces is advisory. The packet is input to a model's
judgment; the findings that come back are filed as suggestions the owner
triages. There is no write path to canon anywhere in this file.

Exit codes: 0 ok, 1 schema violations (validate) / runtime error,
2 usage error.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://discord.com/api/v10"
PAGE = 100                      # Discord's max messages per request
DEFAULT_MAX_PAGES = 20          # 2000 messages/channel/run, then stop loud
MIN_RULING_CHARS = 80           # below this a DM line is chatter, not a ruling
PACKET_CHAR_BUDGET = 120_000    # pre-compress before any model reads

# What the agent is looking for. Each item names the product it serves so
# a finding can be traced to a reason for harvesting at all.
CHECKLIST = [
    {
        "category": "canon-candidate",
        "product": "canon capture",
        "severity": "info",
        "check": "The DM stated something between sessions that the wiki "
                 "does not record — a ruling, a name, a correction, a fact "
                 "about the world. Only messages authored by a configured "
                 "dm_id qualify. A player asserting lore is NOT a "
                 "canon-candidate, however confident they sound.",
        "evidence": "Quote the DM's message and give its channel and "
                    "timestamp. Name the wiki page it belongs on.",
    },
    {
        "category": "gap",
        "product": "gap index",
        "severity": "info",
        "check": "A question the table asked that the wiki cannot answer — "
                 "either the lore bot said so itself (see "
                 "`bot_unanswered`), or a player asked in chat and the "
                 "answer is not on any page. Repeated questions rank "
                 "higher: the table is telling you what to write next.",
        "evidence": "Quote the question. Say which page should have "
                    "answered it, or that no page covers the subject.",
    },
    {
        "category": "naming",
        "product": "naming drift",
        "severity": "info",
        "check": "A proper noun the table types in chat that the wiki "
                 "spells differently or does not contain. Chat spelling is "
                 "usually right and transcript spelling is usually wrong, "
                 "so these feed the transcript glossary as much as the "
                 "wiki.",
        "evidence": "Give both spellings and where each appears.",
    },
    {
        "category": "contradiction",
        "product": "canon capture",
        "severity": "warning",
        "check": "Something said in chat that contradicts a wiki page. "
                 "Report it; do not adjudicate it. If the DM said it, the "
                 "wiki is probably stale; if a player said it, the player "
                 "is probably misremembering — but that call is the "
                 "owner's.",
        "evidence": "Quote both sides and cite the page.",
    },
]

NOT_IN_SCOPE = [
    "Anything the deterministic lint already checks — headings, links, "
    "frontmatter, stubs. This pass reads people, not files.",
    "Player speculation about where the story is going. The wiki records "
    "what the table has established, not what it hopes.",
    "Rewriting human-authored prose. Findings propose; the owner disposes.",
    "Private channels and direct messages. If it is not in the allow-list "
    "it was never fetched, and nothing here should reference it.",
    "Adjudicating contradictions. Surface them and stop.",
]

FINDING_FIELDS = {"category", "severity", "summary", "evidence", "suggestion"}
VALID_CATEGORIES = {c["category"] for c in CHECKLIST}
VALID_SEVERITIES = {"info", "warning", "error"}


# --------------------------------------------------------------- transport

def http_get(url, token, timeout=30):
    """One Discord GET. Isolated so verify can substitute a transport."""
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bot {token}",
                 "User-Agent": "eddic-harvest (+https://github.com/tohuw/eddic)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_with_retry(url, token, transport, tries=3):
    """Discord rate-limits by 429 with a retry_after; honor it."""
    for attempt in range(tries):
        try:
            return transport(url, token)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                try:
                    wait = float(json.loads(
                        e.read().decode("utf-8")).get("retry_after", 1))
                except Exception:
                    wait = 1.0
                time.sleep(min(wait, 30))
                continue
            raise
    raise RuntimeError("unreachable")


# ------------------------------------------------------------------- state

def load_state(path):
    p = Path(path)
    if not p.exists():
        return {"watermarks": {}, "runs": 0}
    state = json.loads(p.read_text(encoding="utf-8"))
    state.setdefault("watermarks", {})
    state.setdefault("runs", 0)
    return state


def save_state(path, state):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")


def assert_no_content(state):
    """The state file is a promise: ids and counts, never words. Enforce
    it rather than documenting it, so a future edit cannot quietly break
    what the table was told."""
    blob = json.dumps(state)
    for key in ("content", "text", "message", "body"):
        if f'"{key}"' in blob:
            raise RuntimeError(
                f"state would carry message text (key {key!r}); refusing")
    return True


# -------------------------------------------------------------- collection

def pull_channel(channel, token, after, transport, max_pages):
    """Ascending fetch of everything after `after`. Returns (msgs, truncated)."""
    out, cursor, truncated = [], after, False
    for page in range(max_pages):
        url = f"{API}/channels/{channel}/messages?limit={PAGE}"
        if cursor:
            url += f"&after={cursor}"
        batch = get_with_retry(url, token, transport)
        if not batch:
            return out, False
        batch.sort(key=lambda m: int(m["id"]))       # API returns newest-first
        out.extend(batch)
        cursor = batch[-1]["id"]
        if len(batch) < PAGE:
            return out, False
        truncated = page == max_pages - 1
    return out, truncated


class MissingIntent(RuntimeError):
    """Discord strips message content for applications without the
    Message Content privileged intent, and it does so silently: the
    messages arrive, complete but wordless. Detected rather than
    documented, because the failure otherwise looks exactly like a quiet
    channel — and the watermark would sail past a window nobody read."""


def looks_wordless(msgs):
    """True when every message came back with nothing readable at all.
    Attachment-only and embed-only messages are legitimately empty, so
    they clear the check on their own."""
    if not msgs:
        return False
    return all(not (m.get("content") or "").strip()
               and not m.get("embeds")
               and not m.get("attachments")
               and not m.get("sticker_items")
               for m in msgs)


def classify(msg, dm_ids, bot_ids):
    author = str((msg.get("author") or {}).get("id", ""))
    if author in dm_ids:
        return "dm"
    if author in bot_ids or (msg.get("author") or {}).get("bot"):
        return "bot"
    return "player"


def normalize(msg, channel_name, dm_ids, bot_ids):
    author = msg.get("author") or {}
    return {
        "id": msg.get("id", ""),
        "channel": channel_name,
        "at": msg.get("timestamp", ""),
        "who": classify(msg, dm_ids, bot_ids),
        "name": author.get("global_name") or author.get("username") or "?",
        "text": (msg.get("content") or "").strip(),
        "reply_to": ((msg.get("referenced_message") or {}).get("id") or ""),
    }


def is_question(text):
    return "?" in text and len(text) > 12


PROPER = re.compile(r"\b([A-Z][a-z]{2,})(?:'[A-Za-z]+)?\b")
STOPWORDS = {
    "The", "This", "That", "There", "Then", "They", "Their", "These",
    "Those", "What", "When", "Where", "Which", "Who", "Why", "How",
    "And", "But", "For", "Not", "You", "Your", "Yes", "Okay", "Also",
    "Just", "Can", "Did", "Does", "Would", "Could", "Should", "Discord",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
    "Sunday", "Session", "Sorry", "Thanks", "Thank", "Hey", "Its",
}


def proper_nouns(records):
    seen = {}
    for r in records:
        if r["who"] == "bot":
            continue
        for tok in PROPER.findall(r["text"]):
            if tok in STOPWORDS or len(tok) < 3:
                continue
            seen[tok] = seen.get(tok, 0) + 1
    return seen


def corpus_words(corpus_dir):
    """Every capitalized token the wiki already knows, so the naming pass
    reports what is genuinely absent rather than everything."""
    known = set()
    root = Path(corpus_dir) if corpus_dir else None
    if not root or not root.is_dir():
        return known
    for f in sorted(root.rglob("*.md")):
        try:
            known.update(PROPER.findall(f.read_text(encoding="utf-8")))
        except OSError:
            continue
    return known


def read_bot_questions(path, unanswered_markers):
    """The lore bot's own log: questions and whether it could answer.
    Absent log is not an error — it just means that product is off."""
    p = Path(path) if path else None
    if not p or not p.exists():
        return [], []
    asked, unanswered = [], []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        q = (row.get("question") or "").strip()
        if not q:
            continue
        asked.append(q)
        answered = row.get("answered")
        if answered is False:
            unanswered.append(q)
            continue
        blob = (row.get("answer") or "").lower()
        if any(m in blob for m in unanswered_markers):
            unanswered.append(q)
    return asked, unanswered


# ------------------------------------------------------------------ packet

def build_packet(records, *, window, truncated, bot_asked, bot_unanswered,
                 novel_nouns, dropped):
    dm = [r for r in records if r["who"] == "dm"]
    rulings = [r for r in dm if len(r["text"]) >= MIN_RULING_CHARS]
    questions = [r for r in records
                 if r["who"] == "player" and is_question(r["text"])]

    packet = {
        "kind": "eddic-harvest-packet",
        "version": 1,
        "window": window,
        "counts": {
            "messages": len(records),
            "dm": len(dm),
            "dm_substantive": len(rulings),
            "player_questions": len(questions),
            "bot_questions": len(bot_asked),
            "bot_unanswered": len(bot_unanswered),
            "novel_proper_nouns": len(novel_nouns),
            "dropped_opted_out": dropped,
        },
        "truncated_channels": truncated,
        "dm_statements": rulings,
        "player_questions": questions,
        "bot_unanswered": bot_unanswered,
        "novel_proper_nouns": novel_nouns,
        "checklist": CHECKLIST,
        "not_in_scope": NOT_IN_SCOPE,
        "findings_schema": {
            "findings": [{
                "category": sorted(VALID_CATEGORIES),
                "severity": sorted(VALID_SEVERITIES),
                "summary": "one sentence, what the wiki should gain or fix",
                "evidence": "quote plus channel and timestamp",
                "suggestion": "the concrete edit to propose, page named",
            }],
        },
    }
    return compress(packet)


def compress(packet):
    """Pre-compress before a model ever sees this. Drop the least
    load-bearing material first, and say what was dropped — a silent cap
    reads as 'nothing else happened', which is a lie."""
    notes = []
    for field, keep in (("player_questions", 60), ("dm_statements", 80)):
        rows = packet.get(field, [])
        if len(rows) > keep:
            packet[field] = rows[-keep:]
            notes.append(f"{field}: kept the {keep} most recent of {len(rows)}")
    while len(json.dumps(packet)) > PACKET_CHAR_BUDGET:
        for field in ("player_questions", "dm_statements"):
            if len(packet.get(field, [])) > 10:
                dropped = len(packet[field]) // 4 or 1
                packet[field] = packet[field][dropped:]
                notes.append(f"{field}: dropped {dropped} oldest for budget")
                break
        else:
            break
    if notes:
        packet["compression_notes"] = notes
    return packet


# -------------------------------------------------------------------- pull

def do_pull(config, state_path, token, transport, max_pages):
    if not config.get("announced"):
        print("harvest is not armed: the table has not been told.\n"
              "  Say in the server what is collected, from which channels, "
              "and what is kept\n"
              "  (the module ships the wording), give people the opt-out, "
              "then set\n"
              "  \"announced\": true in the harvest config. Nothing is "
              "pulled until then.",
              file=sys.stderr)
        return None, 2

    channels = config.get("channels") or {}
    if not channels:
        print("no channels in the allow-list; nothing to harvest",
              file=sys.stderr)
        return None, 2

    dm_ids = {str(i) for i in config.get("dm_ids", [])}
    bot_ids = {str(i) for i in config.get("bot_ids", [])}
    optout = {str(i) for i in config.get("optout_ids", [])}
    state = load_state(state_path)
    watermarks = state["watermarks"]

    records, truncated, dropped, failed = [], [], 0, []
    for chan_id, chan_name in channels.items():
        try:
            msgs, cut = pull_channel(str(chan_id), token,
                                     watermarks.get(str(chan_id)),
                                     transport, max_pages)
        except Exception as e:                      # one bad channel must
            failed.append(f"{chan_name}: {e}")      # not lose the others
            continue
        if looks_wordless(msgs):
            failed.append(
                f"{chan_name}: {len(msgs)} message(s) came back with no "
                "content — the bot application is missing the Message "
                "Content privileged intent (enable it in the Developer "
                "Portal); watermark held")
            continue
        if cut:
            truncated.append(chan_name)
        for m in msgs:
            if str((m.get("author") or {}).get("id", "")) in optout:
                dropped += 1
                continue
            rec = normalize(m, chan_name, dm_ids, bot_ids)
            if rec["text"]:
                records.append(rec)
        if msgs:                                    # advance only on success
            watermarks[str(chan_id)] = msgs[-1]["id"]

    records.sort(key=lambda r: r["at"])
    known = corpus_words(config.get("corpus_dir"))
    nouns = {n: c for n, c in proper_nouns(records).items() if n not in known}
    asked, unanswered = read_bot_questions(
        config.get("question_log"),
        config.get("unanswered_markers",
                   ["archive doesn't say", "archive does not say",
                    "not in the archive", "doesn't record", "no record"]))

    packet = build_packet(
        records,
        window={"from": records[0]["at"] if records else "",
                "to": records[-1]["at"] if records else "",
                "channels": sorted(channels.values()),
                "failed_channels": failed},
        truncated=truncated,
        bot_asked=asked,
        bot_unanswered=unanswered,
        novel_nouns=dict(sorted(nouns.items(), key=lambda kv: -kv[1])[:60]),
        dropped=dropped,
    )

    state["runs"] += 1
    state["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    assert_no_content(state)
    save_state(state_path, state)

    for name in truncated:
        print(f"warning: {name} hit the page cap; more remains for next run",
              file=sys.stderr)
    for f in failed:
        print(f"warning: channel failed, watermark held: {f}", file=sys.stderr)
    return packet, 0


# ---------------------------------------------------------------- validate

def validate_findings(doc):
    errs = []
    if not isinstance(doc, dict) or not isinstance(doc.get("findings"), list):
        return ["document must be an object with a 'findings' list"]
    for i, f in enumerate(doc["findings"]):
        where = f"findings[{i}]"
        if not isinstance(f, dict):
            errs.append(f"{where}: not an object")
            continue
        missing = FINDING_FIELDS - set(f)
        if missing:
            errs.append(f"{where}: missing {sorted(missing)}")
        if f.get("category") not in VALID_CATEGORIES:
            errs.append(f"{where}: category {f.get('category')!r} not in "
                        f"{sorted(VALID_CATEGORIES)}")
        if f.get("severity") not in VALID_SEVERITIES:
            errs.append(f"{where}: severity {f.get('severity')!r} not in "
                        f"{sorted(VALID_SEVERITIES)}")
        for field in ("summary", "evidence", "suggestion"):
            if not str(f.get(field, "")).strip():
                errs.append(f"{where}: {field} is empty")
    return errs


def do_validate(argv):
    src = next((a for a in argv if not a.startswith("--")), None)
    try:
        raw = Path(src).read_text(encoding="utf-8") if src else sys.stdin.read()
        doc = json.loads(raw)
    except (OSError, ValueError) as e:
        print(f"cannot read findings: {e}", file=sys.stderr)
        return 2
    errs = validate_findings(doc)
    for e in errs:
        print(e, file=sys.stderr)
    n = len(doc.get("findings", [])) if isinstance(doc, dict) else 0
    print(f"{n} finding(s), {len(errs)} schema violation(s)")
    return 1 if errs else 0


# -------------------------------------------------------------------- main

def load_config(path):
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    cfg = os.environ.get("EDDIC_CONFIG")
    if cfg and Path(cfg).exists():
        whole = json.loads(Path(cfg).read_text(encoding="utf-8"))
        return whole.get("harvest", {})
    return {}


def main(argv):
    if "--validate" in argv:
        return do_validate([a for a in argv if a != "--validate"])

    opts, i = {}, 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--") and a != "--pull":
            opts[a] = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
            continue
        i += 1

    config = load_config(opts.get("--config"))
    token = (opts.get("--token") or os.environ.get("DISCORD_TOKEN") or "")
    if not token:
        print("no DISCORD_TOKEN (env or --token)", file=sys.stderr)
        return 2

    state_path = opts.get("--state") or config.get(
        "state_file", "harvest-state.json")
    max_pages = int(opts.get("--max-pages") or DEFAULT_MAX_PAGES)

    packet, code = do_pull(config, state_path, token, http_get, max_pages)
    if packet is None:
        return code
    text = json.dumps(packet, indent=2, ensure_ascii=False)
    out = opts.get("--out")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text + "\n", encoding="utf-8")
        c = packet["counts"]
        print(f"wrote {out}: {c['messages']} message(s), "
              f"{c['dm_substantive']} DM statement(s), "
              f"{c['bot_unanswered']} unanswered question(s), "
              f"{c['novel_proper_nouns']} new proper noun(s)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
