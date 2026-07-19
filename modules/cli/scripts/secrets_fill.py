# /// script
# requires-python = ">=3.9"
# ///
"""eddic secrets — fill the campaign's secret slots, locally.

Usage:
    uv run secrets_fill.py [<campaign_dir>] [--file PATH]
    (bare, as a vendored eddic verb: the campaign root comes from
     EDDIC_CONFIG)

Scans the campaign's gitignored variables files (any `variables.txt`
up to two directories deep, plus --file) for empty slots — lines like
`DISCORD_TOKEN=` with no value — and prompts for each with no-echo
input, writing the value straight into the file. Nothing typed is
echoed, printed, or logged; the report shows fingerprints (first 8
characters) only. Press Enter at a prompt to leave a slot empty.

Exit codes: 0 done (even if all skipped), 2 usage error.
"""

import getpass
import os
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def shape_warning(key, secret):
    """Cheap shape checks for well-known token kinds; advisory only —
    vendors change formats, so never refuse, just warn."""
    if "DISCORD" in key and "TOKEN" in key:
        if secret.count(".") != 2 or len(secret) < 50:
            return ("that does not look like a Discord BOT token "
                    "(expected ~70 chars with two dots — the Bot "
                    "page's Reset Token, not the OAuth2 Client "
                    "Secret)")
    if "ANTHROPIC" in key and not secret.startswith("sk-ant-"):
        return "Anthropic API keys start with sk-ant-"
    if "OPENAI" in key and not secret.startswith("sk-"):
        return "OpenAI API keys start with sk-"
    return None


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    opts = dict(zip(argv, argv[1:]))
    root = None
    if os.environ.get("EDDIC_CONFIG"):
        root = Path(os.environ["EDDIC_CONFIG"]).parent.parent
    if args:
        root = Path(args[0])
    if root is None or not root.is_dir():
        print(__doc__.strip(), file=sys.stderr)
        return 2

    files = sorted(p for p in root.glob("*/variables.txt")
                   if ".git" not in p.parts)
    if (root / "variables.txt").is_file():
        files.insert(0, root / "variables.txt")
    if "--file" in opts:
        files.append(Path(opts["--file"]))

    filled = skipped = 0
    for f in files:
        lines = f.read_text(encoding="utf-8").splitlines()
        changed = False
        for i, ln in enumerate(lines):
            if ln.startswith("#") or "=" not in ln:
                continue
            key, _, val = ln.partition("=")
            if val.strip() or not key.strip() or " " in key.strip():
                continue
            rel = f.relative_to(root)
            secret = getpass.getpass(
                f"{key.strip()} for {rel} (Enter to skip): ")
            if not secret:
                skipped += 1
                continue
            hint = shape_warning(key.strip(), secret)
            if hint:
                print(f"  note: {hint} — stored anyway; re-run "
                      f"after blanking the slot if it was the "
                      f"wrong credential")
            lines[i] = f"{key.strip()}={secret}"
            changed = True
            filled += 1
            print(f"  set {key.strip()} ({secret[:8]}…, "
                  f"len {len(secret)})")
        if changed:
            f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"secrets: {filled} filled, {skipped} skipped "
          f"across {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
