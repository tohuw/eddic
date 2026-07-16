"""Pure helpers for the eddic lore bot — no discord, no network at
import time, so these are unit-testable anywhere. bot.py wires them
to the gateway."""

import hashlib
import io
import os
import re
import tarfile
import urllib.request
from pathlib import Path

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md", "log.md"}


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
        parts.append(f"=== {rel} ===\n"
                     + p.read_text(encoding="utf-8", errors="replace").strip())
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
            text = tar.extractfile(member).read().decode("utf-8", "replace")
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
