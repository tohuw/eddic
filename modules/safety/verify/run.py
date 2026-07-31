# /// script
# requires-python = ">=3.9"
# ///
"""Verify the safety module's deterministic floor.

The property that matters is the one a table is trusting: a player may
set a line without the table learning it was theirs. That is why the
master is DM-only and the player copy is generated rather than written —
so the render is the only thing that can produce the shared page, and it
is structurally incapable of emitting a `from:` value. These checks prove
the render drops attribution and dm-only entries, that the schema fails
closed rather than silently dropping an entry players would stop seeing,
and that `check` catches a hand-edited page or a contributor id that
reached any player-facing surface."""

import subprocess
import sys
import tempfile
from pathlib import Path

SAFETY = Path(__file__).resolve().parent.parent / "scripts" / "safety_record.py"
MASTER_REL = "systems/safety.dm.md"
PLAYER_REL = "systems/safety.md"

MASTER = """---
visibility: dm
authorship: human
curation: human
---

# Table safety (DM record)

## Preamble

What this table has agreed to leave out or leave off-screen.

## Signals

Anyone may call a stop, in the room or by private message.

## Changing this

Revisit at the start of any session; changes take effect immediately.

## Record

### Harm to animals

kind: line
share: table
note: Never on-screen and never described.
from: kestrel

### The drowning of the Sunken City

kind: veil
share: table
note: Aftermath only; we do not play the drowning itself.
from: anonymous

### A private matter

kind: line
share: dm-only
note: Do not put the Warden's oath near this.
from: vagrant
"""


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def run(*args):
    return subprocess.run([sys.executable, str(SAFETY), *args],
                          capture_output=True, text=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-safety-verify-"))
    wiki = tmp / "wiki"
    surface = tmp / "player"
    surface.mkdir(parents=True, exist_ok=True)
    write(wiki, MASTER_REL, MASTER)

    checks = []

    r = run("render", "--src", str(wiki))
    page = wiki / PLAYER_REL
    body = page.read_text(encoding="utf-8") if page.is_file() else ""
    checks += [
        (r.returncode == 0, f"render exits 0 (got {r.returncode})"),
        (page.is_file(), "render writes the table's copy"),
        ("visibility: player" in body,
         "the table's copy is marked player-visible"),
        ("kestrel" not in body and "vagrant" not in body,
         "no contributor id reaches the table's copy"),
        ("from:" not in body,
         "the render cannot emit a from: field at all"),
        ("Harm to animals" in body,
         "a shared line reaches the table"),
        ("Sunken City" in body, "a shared veil reaches the table"),
        ("A private matter" not in body
         and "Warden's oath" not in body,
         "a dm-only entry never reaches the table, topic or note"),
    ]

    again = run("render", "--src", str(wiki))
    checks.append((again.returncode == 0 and "already current" in again.stdout,
                   "rendering twice is a no-op, not a rewrite"))

    c = run("check", "--src", str(wiki), "--surface", str(surface))
    checks.append((c.returncode == 0,
                   f"check passes on a rendered record (got {c.returncode})"))

    # A hand-edited player page is the failure this pairing exists to
    # catch: someone fixing a typo there loses it on the next render, and
    # someone adding an entry there is writing canon nobody can see.
    page.write_text(body.replace("Harm to animals", "Harm to beasts"),
                    encoding="utf-8")
    c2 = run("check", "--src", str(wiki), "--surface", str(surface))
    checks.append((c2.returncode == 1 and "edited by hand" in c2.stdout,
                   "check catches a hand-edited table copy"))
    run("render", "--src", str(wiki))

    # An id reaching any player-facing surface is the leak that matters,
    # wherever it came from — a stray note, a published page, anything.
    write(surface, "notes.md", "kestrel asked for the animal line.\n")
    c3 = run("check", "--src", str(wiki), "--surface", str(surface))
    checks.append((c3.returncode == 1 and "attribution leak" in c3.stdout
                   and "kestrel" in c3.stdout,
                   "check catches a contributor id on a player surface"))
    (surface / "notes.md").unlink()

    # `anonymous` attributes nothing, so it must never be swept for —
    # otherwise the word itself becomes an unusable string.
    write(surface, "prose.md", "The veil was set anonymously.\n")
    c4 = run("check", "--src", str(wiki), "--surface", str(surface))
    checks.append((c4.returncode == 0,
                   "'anonymous' is not an attributable id and never trips "
                   "the sweep"))
    (surface / "prose.md").unlink()

    # Schema failures must refuse rather than drop: a dropped entry is a
    # line the table stops seeing, which is the one silent failure here.
    for bad, label in [
        ("kind: line\nshare: table\nnote: n\n",
         "fields before any entry heading"),
        ("### X\n\nkind: sideways\nshare: table\nnote: n\n",
         "an entry whose kind is outside the set"),
        ("### Y\n\nkind: line\nshare: everyone\nnote: n\n",
         "an entry whose share is outside the set"),
        ("### Z\n\nkind: line\nshare: table\n",
         "an entry with no note"),
        ("### Harm to animals\n\nkind: line\nshare: table\n"
         "note: duplicate topic\n", "a repeated topic"),
    ]:
        broken = tmp / f"broken-{abs(hash(label))}"
        write(broken, MASTER_REL, MASTER.rstrip() + "\n\n" + bad)
        b = run("check", "--src", str(broken))
        checks.append((b.returncode == 1,
                       f"schema refuses {label}"))

    # The master claiming player visibility is the one mistake that would
    # publish every attribution at once.
    exposed = tmp / "exposed"
    write(exposed, MASTER_REL, MASTER.replace("visibility: dm",
                                              "visibility: player", 1))
    e = run("check", "--src", str(exposed))
    checks.append((e.returncode == 1 and "DM-only" in e.stdout,
                   "the master may not be marked player-visible"))

    failed = [m for ok, m in checks if not ok]
    for ok, m in checks:
        print(("ok  " if ok else "FAIL"), m)
    if failed:
        return 1
    print("verify ok: safety module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
