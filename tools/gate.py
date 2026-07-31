# /// script
# requires-python = ">=3.9"
# ///
"""The gate: everything that must pass before work lands.

    uv run tools/gate.py            # run it
    uv run tools/gate.py --quick    # floor only (no uv, no e2e)

This is the single definition of "does this pass". Three callers share
it, which is the point: the pre-push hook runs it so a contributor's own
push is gated, a maintainer runs it on a contributed branch before
merging, and the manual cross-OS workflow runs it on three runners. It
used to live as shell inside the hook, which meant the gate only existed
where the hook was installed — and a contributor who never ran
`git config core.hooksPath .githooks` had no gate at all, while the
contract claimed the floor was what let strangers' work merge.

There is deliberately no automatic CI. The floor is cheap, local, and
cross-platform by construction; metered minutes on every push buy
nothing a pre-push hook does not already give, and the full
Linux + macOS + Windows matrix is a manual dispatch for when
portability is actually in question.

Exit 0 all green, 1 something failed, 2 the environment cannot run it.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_REL = ".githooks"


def hooks_active():
    """Whether this clone runs the gate on push. None if git is absent."""
    if not shutil.which("git"):
        return None
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "config",
                              "core.hooksPath"],
                             capture_output=True, text=True)
    except OSError:
        return None
    return out.stdout.strip().endswith(HOOKS_REL)


def step(label, argv, runner):
    print(f"gate: {label}...", flush=True)
    proc = subprocess.run(runner + argv, cwd=str(ROOT))
    if proc.returncode != 0:
        print(f"gate: {label} FAILED", file=sys.stderr)
        return False
    return True


def main(argv):
    quick = "--quick" in argv
    py = [sys.executable]
    uv = shutil.which("uv")

    if not step("contract floor", [str(ROOT / "tools" / "floor.py")], py):
        return 1

    if quick:
        print("gate: floor only (--quick); module verifiers not run")
        return 0

    if not uv:
        print("gate: uv not found — ran the floor only. The module "
              "verifiers need uv (https://docs.astral.sh/uv/); install it "
              "before pushing, or the gate is only half run.",
              file=sys.stderr)
        return 2

    runner = [uv, "run"]
    for label, script in (("module verifiers", "tools/verify_all.py"),
                          ("end-to-end composition", "tools/verify_e2e.py")):
        if not step(label, [str(ROOT / script)], runner):
            return 1

    print("gate: green.")
    if hooks_active() is False:
        print("gate: note — this clone does not run the gate on push. "
              "`uv run tools/dev_setup.py` fixes that once and for good.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
