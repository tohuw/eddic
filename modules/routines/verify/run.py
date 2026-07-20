# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Verify the routines module: the Actions adapter parses as YAML and
implements the freshness contract faithfully (verb order, strict lint
first, refuse-on-error, correct triggers), and the contract file
states all five required sections."""

import sys
from pathlib import Path

import yaml

MOD = Path(__file__).resolve().parent.parent


FIVE_SECTIONS = ("**Purpose.**", "**Idempotency.**", "**Safe to miss.**",
                 "**Safe to double-run.**", "**Refusal behavior.**")


def main():
    contract = (MOD / "templates" / "routine-freshness.md").read_text(
        encoding="utf-8")
    semantic = (MOD / "templates" / "routine-semantic-review.md").read_text(
        encoding="utf-8")
    wf = yaml.safe_load((MOD / "templates" / "gh-actions-freshness.yml")
                        .read_text(encoding="utf-8"))
    steps = wf["jobs"]["freshen"]["steps"]
    runs = [s.get("run", "") for s in steps]
    order = [i for i, r in enumerate(runs) if r]

    def run_index(fragment):
        return next((i for i, r in enumerate(runs) if fragment in r), -1)

    idx = [run_index(f) for f in
           ("lint --strict", "project", "build", "pages deploy",
            "stage", "wrangler deploy")]
    # yaml.safe_load turns bare `on:` into True — a known YAML quirk
    trigger = wf.get("on") or wf.get(True)
    checks = [
        (all(i != -1 for i in idx), "all six contract steps present"),
        (idx == sorted(idx), "steps in the contract's order"),
        (idx[0] == min(i for i in idx if i != -1),
         "strict lint runs first"),
        (not any(s.get("continue-on-error") for s in steps),
         "no continue-on-error: refusals stop the chain"),
        ("wiki/**" in str(trigger) and "contribs/**" in str(trigger),
         "event-driven on wiki and contribs changes"),
        (all(h in contract for h in FIVE_SECTIONS),
         "freshness contract states all five required sections"),
        ("--strict" in contract and "lint" in contract,
         "contract demands strict lint"),
        (all(h in semantic for h in FIVE_SECTIONS),
         "semantic-review contract states all five required sections"),
        ("semantic-review" in semantic and "--validate" in semantic,
         "semantic-review contract builds and validates the packet"),
        ("suggest_edit" in semantic and "eddic suggestions" in semantic,
         "semantic-review contract files findings into the retrieval inbox"),
        (("advisory" in semantic and "never" in semantic
          and "auto" in semantic),
         "semantic-review contract states its advisory-only posture"),
        # The Claude Code Routine (hosted agent) rung is documented and
        # paste-ready: prompt, env var, schedule, domain-allow, fallback.
        ("claude.ai/code/routines" in semantic,
         "names the Claude Code Routine creation locus"),
        (("Routine Prompt (paste-ready)" in semantic
          and "/semantic-review" in semantic),
         "ships a paste-ready routine Prompt wired to the run recipe"),
        ("EDDIC_WITNESS_TOKEN" in semantic,
         "names the witness-token environment variable"),
        (("weekly" in semantic and "1 hour" in semantic),
         "recommends a schedule inside the 1-hour interval floor"),
        ("Allowed domains" in semantic,
         "notes the custom-domain Allowed-domains gotcha"),
        ("PR fallback" in semantic,
         "states the PR fallback when the witness host is blocked"),
    ]
    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print("verify ok: routines module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
