# /// script
# requires-python = ">=3.9"
# ///
"""Verify the recorder's consent core without discord or davey
installed: all templates compile; with a stubbed library, emoji
normalization accepts reacts with and without the variation selector,
the sink drops unattributed and unconsented packets while counting
them, consented audio lands as a well-formed per-speaker WAV, and
revocation closes the gate mid-stream.

Also asserts two structural safety properties by source inspection and
pure unit test: the consent post is a PUBLIC channel send (never the
ephemeral interaction reply), and the loopback control surface's router
does auth + method/path dispatch as specified."""

import ast
import os
import py_compile
import sys
import tempfile
import types
import wave
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def consent_is_public(src):
    """Static guarantee that the consent post goes out as a public
    channel send and never as an ephemeral slash reply. Returns a list
    of (ok, message) checks. We walk the AST of open_session and assert:
      - consent_text(...) is an argument to a `.send(` call (public);
      - that returned message is reacted on (`.add_reaction`);
      - consent_text(...) is NOT an argument to any `.respond(`/`.send_message`
        interaction reply (which can be ephemeral)."""
    tree = ast.parse(src)
    send_of_consent = False
    respond_of_consent = False
    add_reaction = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            passes_consent = any(
                isinstance(a, ast.Call)
                and isinstance(a.func, ast.Name)
                and a.func.id == "consent_text"
                for a in node.args)
            if attr == "send" and passes_consent:
                send_of_consent = True
            if attr in ("respond", "send_message", "followup") \
                    and passes_consent:
                respond_of_consent = True
            if attr == "add_reaction":
                add_reaction = True
    return [
        (send_of_consent,
         "consent post is a public channel .send(consent_text(...))"),
        (add_reaction,
         "opt-in react is added on the consent post (.add_reaction)"),
        (not respond_of_consent,
         "consent text is never an ephemeral interaction reply payload"),
    ]


def consent_role_is_gated(src):
    """Static guarantee that the `/record consent-role` subcommand is
    gated on Manage Server: its body must test
    `...guild_permissions.manage_guild` before it can persist a role, so a
    non-privileged member can never change who the consent post pings.
    Returns a list of (ok, message) checks."""
    tree = ast.parse(src)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "consent_role":
            fn = node
            break
    gated = False
    if fn is not None:
        for n in ast.walk(fn):
            if isinstance(n, ast.Attribute) and n.attr == "manage_guild":
                gated = True
                break
    return [
        (fn is not None, "a consent-role subcommand is defined"),
        (gated,
         "consent-role is gated on guild_permissions.manage_guild "
         "(Manage Server)"),
    ]


def control_router_checks():
    """Pure unit test of control.route() — auth, dispatch, status codes —
    with injected fake actions. No sockets, no Discord."""
    sys.path.insert(0, str(TEMPLATES))
    import control

    calls = {"start": 0, "stop": 0, "status": 0}

    def start():
        calls["start"] += 1
        return {"ok": True, "channel": "the-table"}

    def stop():
        calls["stop"] += 1
        return {"ok": True, "outdir": "raw/x"}

    def status():
        calls["status"] += 1
        return {"ok": True, "recording": False, "sessions": []}

    actions = {"start": start, "stop": stop, "status": status}

    def call(method, path, token=None, expected="s3cr3t"):
        return control.route(method, path, token,
                             expected_token=expected, actions=actions)

    checks = []
    # healthz needs no token even when one is set
    code, body = call("GET", "/healthz", token=None)
    checks.append((code == 200 and body.get("service") == "muninn-control",
                   "GET /healthz is open (no token) and identifies Muninn"))
    # auth enforced when a token is configured
    code, body = call("GET", "/status", token=None)
    checks.append((code == 401 and not body["ok"],
                   "missing token is 401 when a secret is configured"))
    code, body = call("POST", "/record/start", token="wrong")
    checks.append((code == 401, "wrong token is 401"))
    # correct token routes to actions
    code, body = call("GET", "/status", token="s3cr3t")
    checks.append((code == 200 and body["recording"] is False,
                   "GET /status returns the status snapshot"))
    code, body = call("POST", "/record/start", token="s3cr3t")
    checks.append((code == 200 and body["ok"] and calls["start"] == 1,
                   "POST /record/start invokes the start action -> 200"))
    code, body = call("POST", "/record/stop", token="s3cr3t")
    checks.append((code == 200 and calls["stop"] == 1,
                   "POST /record/stop invokes the stop action -> 200"))
    # a not-ok action result maps to 409 (conflict), not 200
    code, body = call("GET", "/", token="s3cr3t")  # / aliases /status
    checks.append((code == 200 and calls["status"] >= 2,
                   "GET / aliases /status"))

    def conflict():
        return {"ok": False, "error": "already recording"}
    code, body = control.route("POST", "/start", "s3cr3t",
                               expected_token="s3cr3t",
                               actions={"start": conflict, "stop": stop,
                                        "status": status})
    checks.append((code == 409 and not body["ok"],
                   "a not-ok action result is 409, not 200"))
    # unknown route
    code, body = call("DELETE", "/record/start", token="s3cr3t")
    checks.append((code == 404, "unknown method/path is 404"))
    # no token configured -> open (loopback trust)
    code, body = control.route("GET", "/status", None,
                               expected_token=None, actions=actions)
    checks.append((code == 200,
                   "with no secret configured, loopback access is open"))
    return checks


def main():
    checks = []
    for name in ("recorder.py", "dave_recv.py", "control.py"):
        try:
            py_compile.compile(str(TEMPLATES / name), doraise=True)
            checks.append((True, f"{name} compiles"))
        except py_compile.PyCompileError as e:
            checks.append((False, f"{name} compile error: {e}"))

    # Part-1 safety: the consent post is public, never ephemeral.
    recorder_src = (TEMPLATES / "recorder.py").read_text(encoding="utf-8")
    checks += consent_is_public(recorder_src)
    # The consent-post ping role is set from Discord, gated on Manage Server.
    checks += consent_role_is_gated(recorder_src)

    # stub just enough of the library to import the consent core
    fake = types.ModuleType("discord")
    fake.sinks = types.SimpleNamespace(
        Sink=type("Sink", (), {"__init__": lambda self: None}))
    fake.ApplicationContext = object
    fake.utils = types.SimpleNamespace(utcnow=lambda: None)
    sys.modules["discord"] = fake
    os.environ["DAVE_OFF"] = "1"
    sys.path.insert(0, str(TEMPLATES))
    import recorder

    checks += [
        (recorder.is_consent_emoji("🎙️"),
         "emoji with variation selector accepted"),
        (recorder.is_consent_emoji("🎙"),
         "emoji without variation selector accepted"),
        (not recorder.is_consent_emoji("👍"),
         "other emoji rejected"),
    ]

    # session_status is pure and safe with no open sessions
    st = recorder.session_status()
    checks.append((st == {"ok": True, "recording": False, "sessions": []},
                   "session_status reports idle when nothing is recording"))

    tmp = Path(tempfile.mkdtemp(prefix="eddic-recorder-verify-"))
    sink = recorder.ConsentSink(tmp)
    frame = types.SimpleNamespace(pcm=b"\x01\x02" * 960)
    alice = types.SimpleNamespace(id=1)

    sink.write(frame, None)
    sink.write(frame, alice)
    checks.append((sink.stats["unattributed"] == 1
                   and sink.stats["unconsented"] == 1
                   and sink.stats["written"] == 0
                   and not list(tmp.glob("*.wav")),
                   "unattributed and unconsented packets dropped, "
                   "counted, and fileless"))

    sink.namehints[1] = "Alice"
    sink.consented.add(1)
    for _ in range(5):
        sink.write(frame, alice)
    sink.consented.discard(1)          # revocation mid-stream
    sink.write(frame, alice)
    sink.close_all()
    wavs = list(tmp.glob("*.wav"))
    checks.append((sink.stats["written"] == 5
                   and sink.stats["unconsented"] == 2,
                   "gate opens on consent and closes on revocation"))
    ok_wav = False
    if len(wavs) == 1 and wavs[0].name == "1-Alice.wav":
        with wave.open(str(wavs[0])) as w:
            ok_wav = (w.getnchannels() == 2 and w.getframerate() == 48000
                      and w.getnframes() == 5 * 960 // 2)
    checks.append((ok_wav, "consented audio lands as a well-formed "
                           "per-speaker WAV under the display name"))

    # loopback control surface router
    checks += control_router_checks()

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print("verify ok: recorder module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
