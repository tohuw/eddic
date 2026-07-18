# /// script
# requires-python = ">=3.9"
# ///
"""eddic discord-setup — reconcile a Discord server to its spec.

Usage:
    uv run discord_setup.py <server-spec.json> [--apply] [--dump]
        [--token-file <variables.txt>] [--api <base>]
    (bare, as a vendored eddic verb: the campaign root comes from
     EDDIC_CONFIG; the spec defaults to <campaign>/server-spec.json
     and the token to <campaign>/bot/variables.txt)

The spec is the campaign's standing record of server shape: roles,
channels, topics, and role-privacy. Default run is a drift report,
lint-style: missing (in spec, not on server), extra (on server, not
in spec), and mismatched (topic/privacy differs). --apply creates
what is missing and never deletes or renames anything — destructive
drift is only ever reported; removal stays a human act in the
Discord client. --dump prints the LIVE server as spec JSON (adopting
an existing server = dump, trim to what you mean, commit).

Auth: DISCORD_TOKEN from the environment or the token file. The bot
needs Manage Roles and Manage Channels (re-invite with those if the
report says 403).

Exit codes: 0 in sync (or applied clean), 1 drift found (report
mode) or apply failed, 2 usage error.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

TEXT, VOICE = 0, 2
TYPE_NAMES = {TEXT: "text", VOICE: "voice"}
VIEW_CHANNEL = 0x400


def api(base, token, method, path, body=None):
    req = urllib.request.Request(
        base + path, method=method,
        headers={"Authorization": f"Bot {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "eddic-discord-setup/0.1"},
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read() or b"null")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200]
        raise RuntimeError(f"{method} {path} -> {e.code}: {detail}")


def load_token(token_file):
    tok = os.environ.get("DISCORD_TOKEN")
    if tok:
        return tok
    if token_file and token_file.is_file():
        for ln in token_file.read_text(encoding="utf-8").splitlines():
            if ln.startswith("DISCORD_TOKEN=") and len(ln) > 15:
                return ln.partition("=")[2].strip()
    return None


def live_state(base, token, guild):
    roles = {r["name"]: r for r in
             api(base, token, "GET", f"/guilds/{guild}/roles")
             if not r.get("managed") and r["name"] != "@everyone"}
    chans = {c["name"]: c for c in
             api(base, token, "GET", f"/guilds/{guild}/channels")
             if c["type"] in TYPE_NAMES}
    return roles, chans


def private_role_of(chan, roles_by_id, everyone_id):
    denied_everyone = allowed = None
    for ow in chan.get("permission_overwrites", []):
        if ow["id"] == everyone_id and int(ow["deny"]) & VIEW_CHANNEL:
            denied_everyone = True
        elif int(ow["allow"]) & VIEW_CHANNEL:
            allowed = roles_by_id.get(ow["id"], {}).get("name")
    return allowed if denied_everyone else None


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a.split("=")[0] for a in argv if a.startswith("--")}
    opts = {}
    it = iter(argv)
    for a in it:
        if a in ("--token-file", "--api"):
            opts[a] = next(it, "")
    spec_path = None
    if os.environ.get("EDDIC_CONFIG"):
        root = Path(os.environ["EDDIC_CONFIG"]).parent.parent
        spec_path = root / "server-spec.json"
        opts.setdefault("--token-file", str(root / "bot" / "variables.txt"))
    if args:
        spec_path = Path(args[0])
    if not spec_path or not spec_path.is_file():
        print(__doc__.strip(), file=sys.stderr)
        return 2
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    guild = str(spec["guild_id"])
    base = opts.get("--api") or "https://discord.com/api/v10"
    token = load_token(Path(opts["--token-file"])
                       if opts.get("--token-file") else None)
    if not token:
        print("no DISCORD_TOKEN in env or token file", file=sys.stderr)
        return 2

    roles, chans = live_state(base, token, guild)
    everyone_id = guild  # @everyone role id == guild id
    all_roles = {r["name"]: r for r in
                 api(base, token, "GET", f"/guilds/{guild}/roles")}
    roles_by_id = {r["id"]: r for r in all_roles.values()}

    if "--dump" in flags:
        out = {"guild_id": guild,
               "roles": [{"name": n} for n in roles],
               "channels": []}
        for name, c in chans.items():
            entry = {"name": name, "type": TYPE_NAMES[c["type"]]}
            if c.get("topic"):
                entry["topic"] = c["topic"]
            priv = private_role_of(c, roles_by_id, everyone_id)
            if priv:
                entry["private_to"] = priv
            out["channels"].append(entry)
        print(json.dumps(out, indent=2))
        return 0

    missing_roles = [r for r in spec.get("roles", [])
                     if r["name"] not in roles]
    missing_chans = [c for c in spec.get("channels", [])
                     if c["name"] not in chans]
    extra_chans = [n for n in chans
                   if n not in {c["name"]
                                for c in spec.get("channels", [])}]
    mismatched = []
    for c in spec.get("channels", []):
        live = chans.get(c["name"])
        if not live:
            continue
        want_priv = c.get("private_to")
        have_priv = private_role_of(live, roles_by_id, everyone_id)
        if want_priv != have_priv:
            mismatched.append((c["name"], "privacy",
                               f"{have_priv} -> {want_priv}"))
        if c.get("topic") and (live.get("topic") or "") != c["topic"]:
            mismatched.append((c["name"], "topic", "differs"))

    if "--apply" not in flags:
        # the default run is the PLAN: what apply will do, what is
        # re-used as-is, and what it deliberately will not decide
        mismatch_names = {name for name, _, _ in mismatched}
        for r in spec.get("roles", []):
            if r["name"] in roles:
                print(f"re-use    role     {r['name']} (exists)")
        for c in spec.get("channels", []):
            if c["name"] in chans and c["name"] not in mismatch_names:
                print(f"re-use    channel  {c['name']} (matches spec)")
        for r in missing_roles:
            print(f"create    role     {r['name']}")
        for c in missing_chans:
            priv = (f", private to {c['private_to']}"
                    if c.get("private_to") else "")
            print(f"create    channel  {c['name']} ({c['type']}{priv})")
        for name, what, detail in mismatched:
            print(f"mismatch  {what:8} {name} — {detail} "
                  f"(owner decides; never auto-repaired)")
        for n in extra_chans:
            print(f"leave     channel  {n} (not in spec; untouched — "
                  f"removal is a human act)")
        drift = bool(missing_roles or missing_chans or mismatched)
        reused = (sum(1 for r in spec.get("roles", [])
                      if r["name"] in roles)
                  + sum(1 for c in spec.get("channels", [])
                        if c["name"] in chans
                        and c["name"] not in mismatch_names))
        print(f"\nPLAN: --apply will create "
              f"{len(missing_roles) + len(missing_chans)} item(s) and "
              f"change nothing else; {reused} re-used as-is, "
              f"{len(mismatched)} mismatch(es) for the owner, "
              f"{len(extra_chans)} extra(s) untouched."
              if drift else
              f"\nin sync: nothing to create; {reused} item(s) "
              f"re-used as-is, {len(extra_chans)} extra(s) untouched.")
        return 1 if drift else 0

    created = []
    for r in missing_roles:
        made = api(base, token, "POST", f"/guilds/{guild}/roles",
                   {"name": r["name"], "hoist": bool(r.get("hoist")),
                    "mentionable": bool(r.get("mentionable"))})
        roles[r["name"]] = made
        created.append(f"role {r['name']}")
    all_roles = {**all_roles, **roles}
    for c in missing_chans:
        body = {"name": c["name"],
                "type": TEXT if c["type"] == "text" else VOICE}
        if c.get("topic"):
            body["topic"] = c["topic"]
        if c.get("private_to"):
            role = roles.get(c["private_to"])
            if not role:
                print(f"apply refused: {c['name']} is private_to "
                      f"unknown role {c['private_to']}", file=sys.stderr)
                return 1
            body["permission_overwrites"] = [
                {"id": everyone_id, "type": 0, "allow": "0",
                 "deny": str(VIEW_CHANNEL)},
                {"id": role["id"], "type": 0,
                 "allow": str(VIEW_CHANNEL), "deny": "0"}]
        api(base, token, "POST", f"/guilds/{guild}/channels", body)
        created.append(f"channel {c['name']}")
    for name in created:
        print(f"created  {name}")
    if mismatched:
        for name, what, detail in mismatched:
            print(f"mismatch (not auto-repaired): {what} on {name} — "
                  f"{detail}")
    print(f"applied: {len(created)} created; extras and mismatches "
          f"reported only")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except RuntimeError as e:
        print(f"discord-setup REFUSED: {e}", file=sys.stderr)
        if "50013" in str(e) or "403" in str(e):
            print("the bot lacks Manage Roles / Manage Channels — "
                  "re-invite it with those permissions (same invite "
                  "URL flow, updated permissions bits); nothing was "
                  "partially applied beyond what was reported",
                  file=sys.stderr)
        sys.exit(1)
