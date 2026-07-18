# /// script
# requires-python = ">=3.9"
# ///
"""Verify the lint module: run the reporter against the fixture wiki
and require exactly the defects the fixture plants, no more, no fewer.
Exits 0 on match, 1 with a diff otherwise."""

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
REPORTER = HERE.parent / "scripts" / "eddic_lint.py"

EXPECTED = Counter({
    "broken-link": 1,        # sunken-city -> ghost-quarter.md
    "broken-anchor": 1,      # sunken-city -> warden.md#no-such-heading
    "absolute-link": 1,      # sunken-city -> /maps/atlas.html
    "missing-h1": 1,         # lost-shrine
    "firewall-breach": 2,    # index and warden link the DM-only vault
    "log-malformed": 2,      # unknown type 'conjure'; freeform ## header
    "orphan": 2,             # lost-shrine; contributed field-notes
    "unreachable": 2,        # lost-shrine; contributed field-notes
    "tiny-unstubbed": 1,     # lost-shrine only — kestrel's overlay
                             # replaced the tiny vault page, proving
                             # the effective view took the overlay
    "contrib-conflict": 1,   # vagrant's second claim on the vault
    "contrib-collision": 1,  # kestrel/lost-shrine lands w/o replaces
    "contrib-replaces-missing": 1,  # ghost-annex shadows nothing
    "contrib-unattributed": 1,      # field-notes marked bare 'human'
    "invalid-transactability": 1,   # lost-shrine 'sellable'
    "derived-from-missing": 1,      # warden derived-from ghost-quarter
})


def main():
    proc = subprocess.run(
        [sys.executable, str(REPORTER), str(HERE / "fixture"), "--json",
         "--contribs", str(HERE / "fixture-contribs")],
        capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        print(f"reporter failed (exit {proc.returncode}):\n{proc.stderr}")
        return 1
    report = json.loads(proc.stdout)
    got = Counter(f["code"] for f in report["findings"])

    if got == EXPECTED and proc.returncode == 1:
        print(f"verify ok: {sum(got.values())} findings, all expected; "
              "exit code signals errors correctly")
        return 0

    if proc.returncode != 1:
        print("FAIL: fixture has errors; reporter should exit 1, "
              f"got {proc.returncode}")
    for code in sorted(set(EXPECTED) | set(got)):
        if EXPECTED[code] != got[code]:
            print(f"FAIL: {code}: expected {EXPECTED[code]}, got {got[code]}")
            for f in report["findings"]:
                if f["code"] == code:
                    print(f"        {f['path']}:{f['line']} — {f['detail']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
