# /// script
# requires-python = ">=3.9"
# ///
"""Set this clone up to gate its own pushes. Run once, after cloning.

    uv run tools/dev_setup.py

Git will not let a repository configure its own hooks — that would let
any clone run code on checkout — so activating them is one command
somebody has to type. This is that command, and it exists because
"activate per clone with `git config core.hooksPath .githooks`" buried in
a contract is a step no contributor performs, which left their pushes
ungated while the contract claimed otherwise.

Idempotent: safe to run whenever, reports what was already true.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ".githooks"


def main(argv):
    ok = True

    if not shutil.which("git"):
        print("dev_setup: git not on PATH — cannot configure hooks",
              file=sys.stderr)
        return 2
    if not (ROOT / HOOKS / "pre-push").is_file():
        print(f"dev_setup: {HOOKS}/pre-push missing — wrong directory?",
              file=sys.stderr)
        return 2

    current = subprocess.run(
        ["git", "-C", str(ROOT), "config", "core.hooksPath"],
        capture_output=True, text=True).stdout.strip()
    if current.endswith(HOOKS):
        print(f"  ok    hooks already active ({current})")
    else:
        r = subprocess.run(["git", "-C", str(ROOT), "config",
                            "core.hooksPath", HOOKS])
        if r.returncode == 0:
            print(f"  ok    hooks activated (core.hooksPath = {HOOKS})")
        else:
            print("  FAIL  could not set core.hooksPath", file=sys.stderr)
            ok = False

    if sys.version_info >= (3, 9):
        print(f"  ok    python {sys.version.split()[0]}")
    else:
        print(f"  FAIL  python >= 3.9 required, found "
              f"{sys.version.split()[0]}", file=sys.stderr)
        ok = False

    if shutil.which("uv"):
        print("  ok    uv on PATH")
    else:
        print("  warn  uv not found — the module verifiers need it "
              "(https://docs.astral.sh/uv/). The floor still runs "
              "without it; the rest of the gate does not.")

    print("\ndev_setup: " + ("ready. Your pushes now run the gate; "
                             "`uv run tools/gate.py` runs it by hand."
                             if ok else "incomplete — see above."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
