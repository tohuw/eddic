"""Pure helpers for the eddic lore bot — no discord, no network at
import time, so these are unit-testable anywhere. bot.py wires them
to the gateway."""

import hashlib
import hmac
import io
import json
import os
import re
import secrets
import tarfile
import time
import urllib.request
from collections import Counter
from pathlib import Path

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md", "log.md"}


# The corpus is served to players, and frontmatter can carry DM-only keys.
# The projection strips it too, but the bot parses it again as
# belt-and-suspenders so it never serves a frontmatter secret even if fed a
# page that still carries one. Stamped from tools/wikilib.py rather than
# hand-written, so the bot's idea of where frontmatter ends cannot drift
# from the projection's — a disagreement here would serve the difference.
# --- BEGIN SHARED wikilib: split_frontmatter ---
def split_frontmatter(text):
    """(frontmatter dict, body) — flat `key: value` pairs only, top level
    only, no YAML dependency. A page with no frontmatter yields ({}, text),
    which is what makes every visibility judgment fail closed."""
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm = {}
                for ln in lines[1:i]:
                    if ":" in ln and not ln.startswith((" ", "\t")):
                        k, _, v = ln.partition(":")
                        fm[k.strip()] = v.strip()
                return fm, "\n".join(lines[i + 1:])
    return {}, text
# --- END SHARED wikilib ---


def load_variables(path):
    """KEY=VALUE file into os.environ with setdefault — real env wins,
    so platform config (Railway, launchd) overrides the file."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def corpus_from_dir(root):
    """Concatenate every content page, each headed by its path, into
    the corpus block the model reads. Input should be the player
    projection — never the DM master."""
    root = Path(root)
    parts = []
    for p in sorted(root.rglob("*.md")):
        if p.name in NON_CONTENT:
            continue
        rel = p.relative_to(root).as_posix()
        _, text = split_frontmatter(
            p.read_text(encoding="utf-8", errors="replace"))
        parts.append(f"=== {rel} ===\n" + text.strip())
    return "\n\n".join(parts)


def dir_fingerprint(root):
    """Cheap change detector for the local freshness poll: hash of
    every content file's path, size, and mtime."""
    root = Path(root)
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.md")):
        if p.name in NON_CONTENT:
            continue
        st = p.stat()
        h.update(f"{p.relative_to(root)}:{st.st_size}:{st.st_mtime_ns}"
                 .encode())
    return h.hexdigest()


def github_head_sha(repo, token, branch="master"):
    """HEAD SHA of the wiki repo — the cloud freshness poll."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/commits/{branch}",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github.sha",
                 "User-Agent": "eddic-lore-bot"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode().strip()


def corpus_from_tarball(repo, token, subdir, branch="master"):
    """Fetch the repo tarball via the API (no git on the host) and
    build the corpus from <subdir> within it."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/tarball/{branch}",
        headers={"Authorization": f"Bearer {token}",
                 "User-Agent": "eddic-lore-bot"})
    with urllib.request.urlopen(req, timeout=120) as res:
        data = res.read()
    parts = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in sorted(tar.getmembers(), key=lambda m: m.name):
            if not member.isfile():
                continue
            # strip the tarball's <org>-<repo>-<sha>/ prefix
            rel = member.name.partition("/")[2]
            if not rel.startswith(subdir.rstrip("/") + "/"):
                continue
            name = rel.rsplit("/", 1)[-1]
            if not name.endswith(".md") or name in NON_CONTENT:
                continue
            _, text = split_frontmatter(
                tar.extractfile(member).read().decode("utf-8", "replace"))
            inner = rel[len(subdir.rstrip("/")) + 1:]
            parts.append(f"=== {inner} ===\n{text.strip()}")
    return "\n\n".join(parts)


def split_message(text, limit=2000):
    """Split on line boundaries under Discord's message limit."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:          # pathological single line
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = line
        else:
            current += line
    if current.strip():
        chunks.append(current)
    return chunks


def strip_bot_mention(content, bot_id):
    return re.sub(rf"<@!?{bot_id}>", "", content).strip()


def page_paths(corpus):
    """Every page path in a corpus block (the `=== path ===` headers).
    Lets a capability notice which pages exist without re-reading disk."""
    return re.findall(r"^=== (.+?) ===$", corpus, re.M)


def page_title(corpus, path):
    """The first `# ` heading of the given page's block, or the path's
    stem titleized if it has none."""
    m = re.search(rf"^=== {re.escape(path)} ===\n(.*?)(?=^=== |\Z)",
                  corpus, re.M | re.S)
    if m:
        h = re.search(r"^#\s+(.+)$", m.group(1), re.M)
        if h:
            return h.group(1).strip()
    stem = path.rsplit("/", 1)[-1].removesuffix(".md")
    return stem.replace("-", " ").title()


def new_session_pages(corpus, announced):
    """Session recap pages present in the corpus but not yet announced.
    A page counts as a session recap if 'sessions/' is in its path.
    Pure: the caller owns the announced set and its persistence."""
    return [p for p in page_paths(corpus)
            if "sessions/" in p and p not in announced]


# ---------------------------------------------------------------------
# What the table asked this week
#
# What players ask is the best signal a DM has about what the table is
# confused by and which hooks it is chasing, and it was being discarded
# on every request. These helpers keep a short, DM-side record of the
# questions and aggregate it into a weekly digest.
#
# The record holds only what the DM could already scroll back and read
# in the channel: the question text, when it was asked, and which pages
# the answer pointed at. No names, no handles, no account ids, no other
# channel messages, no answer text. The one identifier is a one-way tag
# (HMAC of the account id under a salt that stays on the DM's machine),
# which exists solely so a player can say "forget me" and have their
# rows found; nothing reverses it and no digest ever shows it.
# ---------------------------------------------------------------------

QUESTION_KEEP_DAYS = 14         # a digest week plus the week it compares to
QUESTION_TEXT_LIMIT = 300

# Enough English filler to stop "what", "about" and "there" from
# presenting themselves as the table's burning obsessions.
STOPWORDS = frozenset("""
about after again against also anyone anything around because been
before being between both cannot could does doing done down during
each else even ever every from give going gone have here himself
into itself just keep kind know last like made make many maybe mean
more most much must need never next once only other ours over please
really right said same says seem seen should since some someone
something still such sure take tell than that their them then there
these they thing think this those though through time told took
under until upon very want wants were what when where which while
whom will with within without would your yours
""".split())

_WORDS = re.compile(r"[a-z]{4,}")


def utc_stamp(when=None):
    """ISO-8601 UTC to the second. Fixed width, so stamps compare and
    sort as plain strings — no date parsing anywhere in the log path."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ",
                         time.gmtime(time.time() if when is None else when))


def salient_terms(text):
    """Content words of a question, lowercased, filler dropped, crudely
    singularized so 'reaver' and 'reavers' cluster. Deliberately dumb:
    a term is a clustering key for the digest, never a claim about
    meaning."""
    out = []
    for w in _WORDS.findall(text.lower()):
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        if len(w) >= 4 and w not in STOPWORDS:
            out.append(w)
    return out


def corpus_vocabulary(corpus):
    """Every content word the wiki uses, including its page paths. A
    question term absent from this set is a subject the wiki has no
    words for — the gap signal the digest is built on."""
    return set(salient_terms(corpus.replace("/", " ").replace("-", " ")))


def cited_paths(reply, known_paths):
    """Which corpus pages an answer actually pointed at. The bot cites
    by link when a site is published and by page name when it is not,
    so match both the path and the page's name."""
    low = reply.lower()
    found = set()
    for path in known_paths:
        stem = path[:-3] if path.endswith(".md") else path
        name = stem.rsplit("/", 1)[-1]
        if stem.lower() in low or (
                len(name) >= 4 and name != "index"
                and name.replace("-", " ").lower() in low):
            found.add(path)
    return sorted(found)


def asker_tag(account_id, salt):
    """One-way tag for an account. Reversible by nobody; its only job is
    to let 'forget me' find the right rows."""
    return hmac.new(salt.encode("utf-8"), str(account_id).encode("utf-8"),
                    hashlib.sha256).hexdigest()[:16]


def log_salt(path):
    """The tag salt, created on first use and never leaving this host.
    Delete the file and every existing tag becomes unmatchable — which
    is a fine way to end a campaign's record."""
    p = Path(path)
    if p.exists():
        existing = p.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    p.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_hex(16)
    p.write_text(salt + "\n", encoding="utf-8")
    return salt


def read_questions(path):
    """Rows of the question log, skipping anything unparseable — a
    half-written line from a killed process loses one question, never
    the log."""
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("at"), str):
            rows.append(row)
    return rows


def write_questions(path, rows):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                           for r in rows), encoding="utf-8")
    tmp.replace(p)


def question_record(question, cited=(), outcome="answered", who="",
                    when=None, limit=QUESTION_TEXT_LIMIT):
    """One logged question. `outcome` is 'answered' when the reply cited
    a page, 'uncited' when it cited none (the archive had nothing, or
    had it badly), 'failed' when the answer never came."""
    return {"at": utc_stamp(when),
            "q": " ".join(question.split())[:limit],
            "cited": sorted(set(cited)),
            "outcome": outcome,
            "who": who}


def log_question(path, record, keep_days=QUESTION_KEEP_DAYS, when=None):
    """Append one question and drop everything past retention in the
    same pass, so the retention promise holds without a sweeper and
    without the process ever restarting. Returns the surviving rows."""
    base = time.time() if when is None else when
    cutoff = utc_stamp(base - keep_days * 86400)
    rows = [r for r in read_questions(path) if r.get("at", "") >= cutoff]
    rows.append(record)
    write_questions(path, rows)
    return rows


def forget_asker(path, who):
    """Erase one player's questions. Returns how many rows went."""
    rows = read_questions(path)
    kept = [r for r in rows if r.get("who") != who]
    if len(kept) != len(rows):
        write_questions(path, kept)
    return len(rows) - len(kept)


def read_optouts(path):
    p = Path(path)
    if not p.exists():
        return set()
    return {ln.strip() for ln in
            p.read_text(encoding="utf-8").splitlines() if ln.strip()}


def set_optout(path, who, opted_out=True):
    """Add or remove a tag from the never-record list. Returns True when
    the list changed."""
    tags = read_optouts(path)
    changed = (who not in tags) if opted_out else (who in tags)
    if not changed:
        return False
    tags = (tags | {who}) if opted_out else (tags - {who})
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(t + "\n" for t in sorted(tags)), encoding="utf-8")
    return True


def _examples(rows, term, limit=3):
    seen, out = set(), []
    for r in rows:
        q = r.get("q", "")
        if term in salient_terms(q) and q not in seen:
            seen.add(q)
            out.append(q)
            if len(out) == limit:
                break
    return out


def weekly_digest(rows, corpus="", when=None, days=7, top=8):
    """Aggregate a window of logged questions into the DM's digest:
    recurring themes, subjects the wiki has no page for, questions that
    got a poor answer or none, what is newly popular against the window
    before, and which pages the table actually reached.

    Pure — hand it rows and a corpus, get a dict. Counts are what the
    digest asserts; it never guesses why anything was asked."""
    base = time.time() if when is None else when
    start = utc_stamp(base - days * 86400)
    prior_start = utc_stamp(base - 2 * days * 86400)
    window = sorted((r for r in rows if r.get("at", "") >= start),
                    key=lambda r: r["at"])
    prior = [r for r in rows
             if prior_start <= r.get("at", "") < start]

    counts, prior_counts = Counter(), Counter()
    for r in window:
        counts.update(set(salient_terms(r.get("q", ""))))
    for r in prior:
        prior_counts.update(set(salient_terms(r.get("q", ""))))

    def rank(counter):
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

    vocab = corpus_vocabulary(corpus) if corpus else set()
    gap_counts = Counter({t: n for t, n in counts.items()
                          if vocab and t not in vocab})
    poor = [{"q": r.get("q", ""), "at": r["at"],
             "outcome": r.get("outcome", "uncited")}
            for r in window if r.get("outcome", "answered") != "answered"]
    pages = Counter()
    for r in window:
        pages.update(r.get("cited") or [])

    return {
        "from": start, "to": utc_stamp(base), "days": days,
        "asked": len(window),
        "answered": sum(1 for r in window if r.get("outcome") == "answered"),
        "prior_asked": len(prior),
        "themes": [{"term": t, "count": n, "examples": _examples(window, t)}
                   for t, n in rank(counts)[:top] if n > 1],
        "gaps": [{"term": t, "count": n, "examples": _examples(window, t)}
                 for t, n in rank(gap_counts)[:top]],
        "poor": poor[:15],
        "new_topics": ([{"term": t, "count": n} for t, n in rank(counts)[:top]
                        if n > 1 and not prior_counts.get(t)]
                       if prior else []),
        "pages": [{"path": p, "count": n} for p, n in rank(pages)[:top]],
    }


def render_digest(digest):
    """The digest as plain text for the DM. Written for a person, not a
    log reader: every section says what the DM should do with it."""
    d = digest
    if not d["asked"]:
        return ("Nobody asked me anything this week — no questions on "
                "record for the last %d days." % d["days"])
    out = ["**What the table asked this week** (%s to %s)"
           % (d["from"][:10], d["to"][:10]),
           "%d question(s), %d of them answered from a page."
           % (d["asked"], d["answered"])]
    if d["prior_asked"]:
        out.append("The week before: %d." % d["prior_asked"])

    if d["themes"]:
        out.append("\n**What kept coming up**")
        for t in d["themes"]:
            out.append("- %s (%d) — %s" % (t["term"], t["count"],
                                           t["examples"][0]))
    if d["new_topics"]:
        out.append("\n**New this week** (nothing last week)")
        out.append("- " + ", ".join("%s (%d)" % (t["term"], t["count"])
                                    for t in d["new_topics"]))
    if d["gaps"]:
        out.append("\n**Asked about, but the wiki has no words for it** "
                   "— the best page prompts you will get")
        for g in d["gaps"]:
            out.append("- %s (%d) — %s" % (g["term"], g["count"],
                                           g["examples"][0]))
    if d["poor"]:
        out.append("\n**I answered these badly or not at all**")
        for p in d["poor"]:
            out.append("- %s" % p["q"])
    if d["pages"]:
        out.append("\n**Pages the table actually reached**")
        out.append("- " + ", ".join("%s (%d)" % (p["path"], p["count"])
                                    for p in d["pages"]))
    return "\n".join(out)


def digest_due(last_sent, weekday, hour, when=None):
    """True when the weekly digest is owed: the chosen day of the week,
    past the chosen hour, and none sent already today. Pure, so the
    schedule is testable without waiting a week."""
    lt = time.localtime(time.time() if when is None else when)
    today = time.strftime("%Y-%m-%d", lt)
    if last_sent == today:
        return False
    return lt.tm_wday == weekday and lt.tm_hour >= hour
