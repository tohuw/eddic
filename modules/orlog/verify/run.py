# /// script
# requires-python = ">=3.9"
# ///
"""Verify the reconciler's discipline against a fake Ørlǫg CLI:
fork happens before apply, the fork's branch id threads through,
refusals abort with the head untouched and no further calls, and
success names the fork. No real Ørlǫg needed — the discipline is
what this module adds; Ørlǫg itself is upstream's tested code."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "reconcile.py"

FAKE = '''
import json, sys
from pathlib import Path
log = Path(sys.argv[0]).parent / "calls.jsonl"
args = sys.argv[1:]
with log.open("a") as f:
    f.write(json.dumps(args) + "\\n")
cmd = args[0]
if cmd == "fork":
    print(json.dumps({"ok": True, "branch": {"id": "fake-fork-1"}}))
elif cmd == "apply":
    muts = Path(args[2]).read_text()
    if "REFUSE" in muts:
        print(json.dumps({"ok": False,
                          "error": {"message": "constraint violated"}}))
        sys.exit(1)
    print(json.dumps({"ok": True, "applied": 1}))
elif cmd == "validate":
    print(json.dumps({"ok": True, "problems": []}))
'''


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-orlog-verify-"))
    fake = tmp / "fake_orlog.py"
    fake.write_text(FAKE, encoding="utf-8")
    calls = tmp / "calls.jsonl"
    good = tmp / "good.json"
    good.write_text('[{"kind": "event.create"}]', encoding="utf-8")
    bad = tmp / "bad.json"
    bad.write_text('[{"kind": "REFUSE-me"}]', encoding="utf-8")
    env = dict(os.environ,
               ORLOG_CMD=f'"{Path(sys.executable).as_posix()}" '
                         f'"{fake.as_posix()}"')

    def run(*args):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, env=env)

    p = run(str(tmp / "story"), str(good), "--name", "test-fork")
    if not calls.exists():
        print(f"FAIL: fake orlog never invoked. reconcile rc="
              f"{p.returncode}\nstdout: {p.stdout}\nstderr: {p.stderr}")
        return 1
    seq = [json.loads(l)[0] for l in calls.read_text().splitlines()]
    branch_args = [json.loads(l) for l in calls.read_text().splitlines()]
    checks = [
        (p.returncode == 0, f"clean reconcile exits 0 (got {p.returncode})"),
        (seq == ["fork", "apply", "validate"],
         f"fork before apply before validate (got {seq})"),
        (all("--branch" in a and "fake-fork-1" in a
             for a in branch_args if a[0] in ("apply", "validate")),
         "the fork's branch id threads through apply and validate"),
        ("fake-fork-1" in p.stdout and "head untouched" in p.stdout,
         "success names the fork and the untouched head"),
        ("owner" in p.stdout, "merging stated as the owner's act"),
    ]

    calls.write_text("", encoding="utf-8")
    p = run(str(tmp / "story"), str(bad))
    seq = [json.loads(l)[0] for l in calls.read_text().splitlines()]
    checks += [
        (p.returncode == 1, f"refusal exits 1 (got {p.returncode})"),
        (seq == ["fork", "apply"],
         f"no validate after a refused apply (got {seq})"),
        ("REFUSED" in p.stderr and "untouched" in p.stderr,
         "refusal is loud and names the untouched head"),
    ]

    p = run(str(tmp / "story"), str(tmp / "missing.json"))
    checks.append((p.returncode == 2, "missing mutations file is usage error"))

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print("verify ok: orlog module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
