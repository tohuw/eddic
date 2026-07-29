# /// script
# requires-python = ">=3.9"
# ///
"""Verify the sale-build fence: refuses without an author, refuses on
uncleared and stale contributions and unconsented transcripts, clears
via hash-pinned consent entries, bundles the right pages (DM pages in,
local-only out, credits injected), and detects drift after sign-off."""

import subprocess
import sys
import tempfile
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent.parent / "scripts" / "bundle.py"


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def run(*args):
    return subprocess.run([sys.executable, str(BUNDLE), *args],
                          capture_output=True, text=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-contribs-verify-"))
    wiki, contribs = tmp / "wiki", tmp / "contribs"
    out = tmp / "bundle"
    base = ["--src", str(wiki), "--contribs", str(contribs),
            "--out", str(out)]

    write(wiki, "index.md",
          "---\nvisibility: player\nauthorship: human\n"
          "transactability: transactable\n---\n\n"
          "# Realm\n\n[Keep](keep.md) [Vault](vault.md)\n")
    write(wiki, "keep.md",
          "---\nvisibility: player\nauthorship: human\n"
          "transactability: transactable\n---\n\n"
          "# The Keep\n\nBase garrison text.\n")
    write(wiki, "vault.md",
          "---\nauthorship: human\ntransactability: transactable\n---\n\n"
          "# The Vault\n\nDM-only page; still ships in a sale.\n")
    write(wiki, "houserules.md",
          "---\nvisibility: player\ntransactability: local-only\n---\n\n"
          "# House Rules\n\nBook content taught to the campaign.\n")
    write(wiki, "srd-bit.md",
          "---\nvisibility: player\nauthorship: human\n"
          "transactability: transactable-with-attribution\n"
          "attribution: Portions from the Example Reference Document "
          "(CC-BY-4.0)\n---\n\n# Reference Bit\n\nLicensed material.\n")
    write(wiki, "keep-revised.md",
          "---\nvisibility: player\nauthorship: human\n"
          "transactability: transactable\n"
          "derived-from: keep.md\n---\n\n"
          "# The Keep, Revised\n\nThe author's improvement.\n")
    # The two pen-axis refusals, each planted with a different remedy.
    write(wiki, "recap-s1.md",
          "---\nvisibility: player\nauthorship: machine\n"
          "transactability: transactable\n---\n\n"
          "# Session One, Recapped\n\nThe agent's own prose.\n")
    write(wiki, "gazetteer.md",
          "---\nvisibility: player\ntransactability: transactable\n---\n\n"
          "# Gazetteer\n\nSellable, but nobody says who wrote it.\n")
    write(wiki, "sessions/s1.md",
          "---\nauthorship: transcript\n"
          "transactability: transactable\n---\n\n"
          "# Session One\n\nThe table's own words.\n")
    write(wiki, "log.md", "# Log\n")
    write(contribs, "kestrel/keep.md",
          "---\nvisibility: player\nauthorship: kestrel\n"
          "replaces: keep.md\ntransactability: transactable\n---\n\n"
          "# The Keep\n\nKestrel's garrison rewrite.\n")
    write(tmp, "AGENTS.md", "# campaign schema stub\n")

    checks = []

    p = run(*base)
    checks.append((p.returncode == 1 and "no author" in p.stderr,
                   "refuses without a declared author"))

    p = run(*base, "--author", "aria")
    checks.append((p.returncode == 1 and "kestrel" in p.stderr,
                   "uncleared contributor refuses the bundle"))
    checks.append(("keep-revised.md" in p.stderr,
                   "taint propagates through derived-from"))
    checks.append(("table" in p.stderr,
                   "transcript page needs full-table consent"))
    checks.append(("recap-s1.md" in p.stderr and "machine" in p.stderr,
                   "machine-authored page refuses a sale"))
    checks.append(("gazetteer.md" in p.stderr and "unmarked" in p.stderr,
                   "unmarked authorship refuses a sale"))
    checks.append((not out.exists(), "refusal wrote nothing"))

    # Both remedies the refusals name: rewrite the machine page with its
    # writer until it is honestly mixed, or unmark the sale and keep the
    # page local. Neither is a re-marking of machine prose as human.
    write(wiki, "recap-s1.md",
          "---\nvisibility: player\nauthorship: mixed\n"
          "transactability: transactable\n---\n\n"
          "# Session One, Recapped\n\nReworked in the DM's own words.\n")
    write(wiki, "gazetteer.md",
          "---\nvisibility: player\n---\n\n"
          "# Gazetteer\n\nSellable, but nobody says who wrote it.\n")

    r = run(*base, "--receipts", "kestrel")
    checks.append((r.returncode == 0 and "sha256:" in r.stdout
                   and "consent | kestrel" in r.stdout,
                   "receipt carries hashes and a ready consent entry"))
    entry = r.stdout[r.stdout.index("## ["):]
    log = wiki / "log.md"
    log.write_text(log.read_text(encoding="utf-8") + "\n"
                   + entry.replace("consent |", "attribution |", 1)
                   + "\n" + entry + "\n"
                   + "## [2026-07-18] consent | table cleared session "
                   "transcripts\n\n(full-table sign-off recorded)\n",
                   encoding="utf-8")

    p = run(*base, "--author", "aria")
    body = ((out / "wiki/keep.md").read_text(encoding="utf-8")
            if (out / "wiki/keep.md").exists() else "")
    checks += [
        (p.returncode == 0, f"cleared bundle exits 0 (got {p.returncode}"
                            f"): {p.stderr.strip()[:120]}"),
        ("Kestrel's garrison rewrite" in body,
         "cleared overlay ships in the bundle"),
        ((out / "wiki/vault.md").exists(),
         "DM-only page ships (visibility never filters a sale)"),
        (not (out / "wiki/houserules.md").exists(),
         "local-only excluded silently"),
        ((out / "wiki/recap-s1.md").exists(),
         "rewritten-to-mixed page ships (the interview remedy)"),
        (not (out / "wiki/gazetteer.md").exists(),
         "unmarked page dropped from the sale, kept in the campaign"),
        ((out / "wiki/sessions/s1.md").exists(),
         "transcript ships under table consent"),
        ("Example Reference Document" in
         ((out / "CREDITS.md").read_text(encoding="utf-8")
          if (out / "CREDITS.md").exists() else ""),
         "attribution credit injected"),
        ((out / "AGENTS.md").exists(), "campaign instructions ship"),
        (not (out / "wiki/log.md").exists(), "operation log stays home"),
    ]

    c = run(*base, "--check")
    checks.append((c.returncode == 0, "check: full = pure + log"))

    write(contribs, "kestrel/keep.md",
          "---\nvisibility: player\nauthorship: kestrel\n"
          "replaces: keep.md\ntransactability: transactable\n---\n\n"
          "# The Keep\n\nKestrel edited after signing off.\n")
    p = run(*base, "--author", "aria")
    checks.append((p.returncode == 1 and "stale clearance" in p.stderr,
                   "post-consent drift refuses (hashes pin sign-off)"))
    c = run(*base, "--check")
    checks.append((c.returncode == 1 and "drift" in c.stderr,
                   "check catches attribution drift"))

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print("verify ok: contribs module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
