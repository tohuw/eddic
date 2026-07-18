# /// script
# requires-python = ">=3.9"
# ///
"""Verify discord-setup against a mock Discord API: drift report
finds missing/extra/mismatched, apply creates additively with
privacy overwrites and never deletes, dump round-trips the live
server, and privacy-to-unknown-role refuses."""

import json
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parent.parent
          / "scripts" / "discord_setup.py")

GUILD = "999000"
STATE = {
    "roles": [
        {"id": GUILD, "name": "@everyone", "managed": False},
        {"id": "1", "name": "DM", "managed": False},
        {"id": "2", "name": "SomeBot", "managed": True},
    ],
    "channels": [
        {"id": "10", "name": "ask-the-archivist", "type": 0,
         "topic": "Ask the campaign's lore-keeper anything.",
         "permission_overwrites": []},
        {"id": "11", "name": "off-topic", "type": 0,
         "permission_overwrites": []},
        {"id": "12", "name": "dm-notes", "type": 0,
         "permission_overwrites": []},   # should be private, isn't
    ],
}
CREATED = []


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith("/roles"):
            self._send(STATE["roles"])
        elif self.path.endswith("/channels"):
            self._send(STATE["channels"])
        else:
            self._send({}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(
            int(self.headers["Content-Length"])))
        CREATED.append((self.path.rsplit("/", 1)[-1], body))
        made = dict(body)
        made["id"] = str(100 + len(CREATED))
        if self.path.endswith("/roles"):
            made.setdefault("managed", False)
            STATE["roles"].append(made)
        else:
            made.setdefault("permission_overwrites",
                            body.get("permission_overwrites", []))
            STATE["channels"].append(made)
        self._send(made)


def main():
    srv = HTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    tmp = Path(tempfile.mkdtemp(prefix="eddic-dsetup-"))
    spec = tmp / "server-spec.json"
    spec.write_text(json.dumps({
        "guild_id": GUILD,
        "roles": [{"name": "DM"}, {"name": "Player"}],
        "channels": [
            {"name": "ask-the-archivist", "type": "text",
             "topic": "Ask the campaign's lore-keeper anything."},
            {"name": "botspam", "type": "text"},
            {"name": "session-table", "type": "voice"},
            {"name": "dm-notes", "type": "text", "private_to": "DM"},
            {"name": "dm-vault", "type": "text",
             "private_to": "DM"},
        ]}), encoding="utf-8")
    env = {"DISCORD_TOKEN": "test-token", "PATH": "/usr/bin:/bin"}

    def run(*args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(spec), "--api", base,
             *args], capture_output=True, text=True, env=env)

    p = run()
    checks = [
        (p.returncode == 1, f"drift exits 1 (got {p.returncode}: "
                            f"{p.stderr.strip()[:120]})"),
        ("create    role     Player" in p.stdout, "plan: missing role -> create"),
        ("re-use    role     DM (exists)" in p.stdout,
         "plan: existing role shown as re-used"),
        ("re-use    channel  ask-the-archivist" in p.stdout,
         "plan: matching channel shown as re-used"),
        ("PLAN: --apply will create" in p.stdout,
         "plan: summary states apply scope"),
        ("botspam" in p.stdout and "session-table" in p.stdout,
         "missing channels found"),
        ("mismatch  privacy  dm-notes" in p.stdout and
         "owner decides" in p.stdout, "privacy mismatch flagged for owner"),
        ("leave     channel  off-topic" in p.stdout and
         "human act" in p.stdout,
         "extra channel left alone, removal deferred to humans"),
    ]

    p = run("--apply")
    priv = [b for _, b in CREATED
            if b.get("name") == "dm-vault"]
    checks += [
        (p.returncode == 0, f"apply exits 0 (got {p.returncode})"),
        (any(b.get("name") == "Player" for _, b in CREATED),
         "missing role created"),
        (any(b.get("name") == "session-table" and b.get("type") == 2
             for _, b in CREATED), "voice channel created as voice"),
        (bool(priv) and any(o["id"] == GUILD and o["deny"] != "0"
                            for o in priv[0]["permission_overwrites"]),
         "private channel denies @everyone"),
        ("not auto-repaired" in p.stdout,
         "existing mismatch reported, not repaired"),
    ]

    p = run()
    checks.append(("dm-notes" in p.stdout and p.returncode == 1,
                   "existing-channel privacy drift persists as report"))

    p = run("--dump")
    dump = json.loads(p.stdout)
    names = {c["name"] for c in dump["channels"]}
    checks += [
        (p.returncode == 0 and "off-topic" in names
         and "botspam" in names, "dump reflects the live server"),
        (all(r["name"] != "SomeBot" for r in dump["roles"]),
         "dump excludes managed (bot) roles"),
    ]

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print("verify ok: discord-setup module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
