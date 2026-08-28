# /// script
# requires-python = ">=3.9"
# ///
"""eddic roster — who a Discord user is, in one place the whole
campaign reads.

Usage:
    uv run roster.py                       list the roster
    uv run roster.py --resolve LABEL...    map labels to canonical names
    uv run roster.py --seed-craig FILE     seed from a Craig info.txt
    uv run roster.py --set ID [--player P] [--character C] [--label L]
                     [--username U] [--alias A] [--role player|dm|guest]
    uv run roster.py --check               validate shape; exit 1 if bad
    (bare, as a vendored eddic verb: the roster path comes from
     EDDIC_ROOT/.eddic/roster.json unless --roster says otherwise.)

Every session, several modules independently re-derive who a Discord
user is and none of it persists: a Craig export names tracks by
username (`5-theseous.flac`), a self-hosted recorder may use display
names, convene and the recorder hold raw user IDs with no name attached,
and reconciling any of that to the table's characters is hand work the
owner has already done before. This is the durable answer, keyed by the
one identifier that does not change — the numeric Discord user id.
Usernames change, display names change, characters get replaced; the id
is stable.

**The roster is DM-tier.** It holds real first names and Discord
handles, and it never reaches the player projection: the wiki module's
firewall does not carry it, and consumers resolve *through* it to a
character label rather than copying it. A transcript should say
"Niðrerir", not "Niðrerir_Ron" and not "tohuw" — which is the point of
the `label` field, and the reason `resolve()` prefers it.

Exit codes: 0 ok, 1 validation failure, 2 usage error.
"""

import json
import os
import re
import sys
from pathlib import Path

ROLES = ("player", "dm", "guest")


# ------------------------------------------------------------------ load

def roster_path(explicit=None):
    if explicit:
        return Path(explicit)
    root = os.environ.get("EDDIC_ROOT")
    if root:
        return Path(root) / ".eddic" / "roster.json"
    return Path(".eddic/roster.json")


def load(path):
    p = Path(path)
    if not p.exists():
        return {"players": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("players", [])
    return data


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(data.get("players", []),
                  key=lambda r: (r.get("role") != "dm", r.get("label", "")))
    data["players"] = rows
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")


def check(data):
    errs, seen = [], set()
    for i, row in enumerate(data.get("players", [])):
        where = f"players[{i}]"
        rid = str(row.get("discord_id", "")).strip()
        if not rid.isdigit():
            errs.append(f"{where}: discord_id must be the numeric id")
        if rid in seen:
            errs.append(f"{where}: duplicate discord_id {rid}")
        seen.add(rid)
        if not str(row.get("label", "")).strip():
            errs.append(f"{where}: label is what everything else prints; "
                        f"it cannot be empty")
        role = row.get("role", "player")
        if role not in ROLES:
            errs.append(f"{where}: role {role!r} not in {list(ROLES)}")
    return errs


# --------------------------------------------------------------- resolve

def _norm(s):
    """Compare on letters and digits only, case-folded, so `5-theseous`,
    `Theseous`, and `theseous.flac` are the same key — and so a track
    label like `Thorne_Ashenpaw_Roger` can be found by its parts."""
    return re.sub(r"[^0-9a-z]+", "", str(s).lower())


def _keys(row):
    """Every string this person is known by, longest first so the most
    specific match wins."""
    out = [row.get("discord_id"), row.get("discord_username"),
           row.get("label"), row.get("player")]
    out += list(row.get("characters") or [])
    out += list(row.get("aliases") or [])
    return [k for k in out if k]


def resolve(label, data, default=None):
    """Map any identifier a module happens to hold — a Craig track stem,
    a display name, a raw user id — to the campaign's canonical label.
    Returns `default` (or the input) when nobody matches, because an
    unknown speaker is a real thing and must not become a wrong one."""
    if label is None:
        return default
    stem = re.sub(r"^\d+[-_]", "", str(label)).strip()   # Craig's `5-name`
    stem = re.sub(r"\.(flac|wav|mp3|m4a|ogg|opus|aac|json)$", "", stem, flags=re.I)
    target = _norm(stem)
    if not target:
        return default if default is not None else label

    best, best_len = None, 0
    for row in data.get("players", []):
        for key in _keys(row):
            k = _norm(key)
            if not k:
                continue
            if k == target or target.startswith(k) or k.startswith(target) \
                    or k in target:
                if len(k) > best_len:
                    best, best_len = row, len(k)
    if best:
        return best.get("label") or best.get("discord_username") or label
    return default if default is not None else label


# ------------------------------------------------------------------ seed

CRAIG_LINE = re.compile(r"^\s*(?P<track>\d+)?[\s:.\-]*"
                        r"(?P<name>.+?)\s*[\(\[]\s*(?P<id>\d{5,})\s*[\)\]]")


def seed_craig(text, data):
    """A Craig export ships an info.txt listing `username (id)` per
    track. That is exactly the pair this facility is missing, so seeding
    is free — the owner then names the characters once."""
    added, known = [], {str(r.get("discord_id")) for r in data["players"]}
    for line in text.splitlines():
        m = CRAIG_LINE.match(line)
        if not m:
            continue
        did, name = m.group("id"), m.group("name").strip()
        if did in known:
            continue
        known.add(did)
        row = {"discord_id": did, "discord_username": name,
               "player": "", "characters": [], "label": name,
               "role": "player"}
        data["players"].append(row)
        added.append(row)
    return added


# ------------------------------------------------------------------ main

def _opts(argv):
    opts, rest, i = {}, [], 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            nxt = argv[i + 1] if i + 1 < len(argv) else ""
            if nxt.startswith("--") or not nxt:
                opts[a] = True
                i += 1
            else:
                opts.setdefault(a, []).append(nxt) if a == "--alias" \
                    else opts.__setitem__(a, nxt)
                i += 2
            continue
        rest.append(a)
        i += 1
    return opts, rest


def main(argv):
    opts, rest = _opts(argv)
    path = roster_path(opts.get("--roster") if isinstance(
        opts.get("--roster"), str) else None)
    data = load(path)

    if "--check" in opts:
        errs = check(data)
        for e in errs:
            print(e, file=sys.stderr)
        print(f"{len(data['players'])} roster entr(ies), {len(errs)} problem(s)")
        return 1 if errs else 0

    if "--resolve" in opts:
        labels = rest or ([opts["--resolve"]]
                          if isinstance(opts["--resolve"], str) else [])
        if not labels:
            print("--resolve needs at least one label", file=sys.stderr)
            return 2
        for label in labels:
            print(f"{label}\t{resolve(label, data)}")
        return 0

    if "--seed-craig" in opts:
        src = opts["--seed-craig"]
        if not isinstance(src, str):
            print("--seed-craig needs a file", file=sys.stderr)
            return 2
        added = seed_craig(Path(src).read_text(encoding="utf-8"), data)
        save(path, data)
        print(f"seeded {len(added)} new entr(ies) from {src}")
        for row in added:
            print(f"  {row['discord_id']}  {row['discord_username']} "
                  f"— name the character with --set")
        return 0

    if "--set" in opts:
        did = str(opts["--set"]).strip()
        if not did.isdigit():
            print("--set needs a numeric Discord user id", file=sys.stderr)
            return 2
        row = next((r for r in data["players"]
                    if str(r.get("discord_id")) == did), None)
        if row is None:
            row = {"discord_id": did, "discord_username": "", "player": "",
                   "characters": [], "label": "", "role": "player"}
            data["players"].append(row)
        for flag, key in (("--player", "player"), ("--label", "label"),
                          ("--username", "discord_username"),
                          ("--role", "role")):
            if isinstance(opts.get(flag), str):
                row[key] = opts[flag]
        if isinstance(opts.get("--character"), str):
            row["characters"] = [opts["--character"]]
            row.setdefault("label", "") or row.update(
                {"label": opts["--character"]})
        for alias in (opts.get("--alias") or []):
            row.setdefault("aliases", [])
            if alias not in row["aliases"]:
                row["aliases"].append(alias)
        if not row.get("label"):
            row["label"] = (row.get("characters") or [""])[0] \
                or row.get("discord_username") or did
        errs = check(data)
        if errs:
            for e in errs:
                print(e, file=sys.stderr)
            return 1
        save(path, data)
        print(f"{row['label']}  ({row['discord_id']}) recorded")
        return 0

    rows = data.get("players", [])
    if not rows:
        print(f"no roster at {path} — seed one with --seed-craig or --set")
        return 0
    width = max(len(str(r.get("label", ""))) for r in rows)
    for r in rows:
        chars = ", ".join(r.get("characters") or []) or "—"
        print(f"{str(r.get('label','')):<{width}}  {r.get('role','player'):<6} "
              f"{r.get('discord_username','') or '—':<18} {chars}")
    print(f"\n{len(rows)} entr(ies) — DM-tier; never projected")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
