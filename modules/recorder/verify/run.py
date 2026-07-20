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
import json
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


def commands_are_permission_gated(src):
    """Static guarantee of the permission model. Gating is Discord-native:
    the `record` command group is created with
    `default_member_permissions=discord.Permissions(manage_guild=True)`, so
    by default only Manage-Server members see or run any `/record`
    subcommand (a server admin grants specific roles via Discord's
    Integrations command-permissions UI). We assert both that the group
    carries that default AND that no handler does its own in-code
    permission check (`guild_permissions` / `manage_guild`), since the
    model deliberately moved gating out of the handlers. Returns a list of
    (ok, message) checks."""
    tree = ast.parse(src)
    group_gated = False
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "create_group"):
            continue
        for kw in node.keywords:
            if kw.arg != "default_member_permissions":
                continue
            v = kw.value
            if (isinstance(v, ast.Call)
                    and isinstance(v.func, ast.Attribute)
                    and v.func.attr == "Permissions"
                    and any(k.arg == "manage_guild"
                            and isinstance(k.value, ast.Constant)
                            and k.value.value is True
                            for k in v.keywords)):
                group_gated = True
    # No handler should reference a permission check anymore.
    handlers_clean = not any(
        isinstance(n, ast.Attribute)
        and n.attr in ("manage_guild", "guild_permissions")
        for n in ast.walk(tree))
    return [
        (group_gated,
         "the /record group sets default_member_permissions=Manage Server "
         "(Discord-native gating on every subcommand)"),
        (handlers_clean,
         "no handler does an in-code permission check — gating is "
         "Discord-native, admins override via the Integrations UI"),
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
    # Operating the recorder is gated Discord-natively on the command group.
    checks += commands_are_permission_gated(recorder_src)

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

    # Feature: recording-suffix nickname computation (pure, 32-char cap).
    suffix = recorder.NICK_SUFFIX
    checks.append((recorder.apply_recording_suffix("Muninn")
                   == "Muninn" + suffix,
                   "short base gets the recording suffix appended verbatim"))
    long_base = "X" * 40
    capped = recorder.apply_recording_suffix(long_base)
    checks.append((len(capped) == recorder.NICK_MAX
                   and capped.endswith(suffix),
                   "over-long base is truncated so base+suffix is exactly 32, "
                   "suffix preserved"))
    checks.append((all(len(recorder.apply_recording_suffix("Y" * n))
                       <= recorder.NICK_MAX
                       for n in range(0, 60)),
                   "the suffixed nick never exceeds 32 chars for any base"))
    once = recorder.apply_recording_suffix("Muninn")
    checks.append((recorder.apply_recording_suffix(once) == once,
                   "applying the suffix to an already-suffixed nick is "
                   "idempotent (no double-append)"))
    checks.append((recorder.strip_recording_suffix("Muninn" + suffix)
                   == "Muninn",
                   "stripping the suffix recovers the base"))
    checks.append((recorder.strip_recording_suffix("Muninn") == "Muninn",
                   "stripping a nick without the suffix is a no-op "
                   "(idempotent)"))

    # Feature: empty-channel disconnect decision (pure arm/cancel).
    bot_m = types.SimpleNamespace(bot=True)
    human = types.SimpleNamespace(bot=False)
    checks.append((recorder.channel_is_empty([]),
                   "a channel with no members is empty (arm the timer)"))
    checks.append((recorder.channel_is_empty([bot_m, bot_m]),
                   "a channel with only bots is empty (arm the timer)"))
    checks.append((not recorder.channel_is_empty([bot_m, human]),
                   "one non-bot member present ⇒ not empty (cancel/hold)"))

    # Feature: settings file round-trip and legacy back-compat migration.
    sdir = Path(tempfile.mkdtemp(prefix="eddic-recorder-settings-"))
    spath = sdir / "recorder_settings.json"
    recorder.save_settings({"consent_ping_role_id": 111,
                            "empty_disconnect_seconds": 45}, path=spath)
    got = recorder.load_settings(path=spath)
    checks.append((got == {"consent_ping_role_id": 111,
                           "empty_disconnect_seconds": 45},
                   "settings file round-trips both keys"))
    recorder.save_settings({"consent_ping_role_id": None}, path=spath)
    got = recorder.load_settings(path=spath)
    checks.append((got["consent_ping_role_id"] is None
                   and got["empty_disconnect_seconds"] == 45,
                   "a None update clears one key and leaves the other"))
    fresh = recorder.load_settings(path=sdir / "does-not-exist.json",
                                   legacy=sdir / "no-legacy.json")
    checks.append((fresh == {"consent_ping_role_id": None,
                             "empty_disconnect_seconds": None},
                   "a missing settings file loads as all-None defaults"))
    # Back-compat: no settings file, but the old consent_ping.json exists —
    # its role_id migrates into consent_ping_role_id (read-only).
    legacy = sdir / "consent_ping.json"
    legacy.write_text(json.dumps({"role_id": 777}), encoding="utf-8")
    migrated = recorder.load_settings(path=sdir / "still-missing.json",
                                      legacy=legacy)
    checks.append((migrated["consent_ping_role_id"] == 777
                   and migrated["empty_disconnect_seconds"] is None,
                   "legacy consent_ping.json role_id migrates when no "
                   "settings file exists"))

    # Feature: empty-timeout parse/validate (pure).
    ok0, v0 = recorder.parse_empty_timeout(0)
    checks.append((ok0 and v0 == 0,
                   "empty-timeout 0 is accepted (disables auto-stop)"))
    ok1, v1 = recorder.parse_empty_timeout("120")
    checks.append((ok1 and v1 == 120,
                   "empty-timeout parses a numeric string to an int"))
    okc, vc = recorder.parse_empty_timeout(recorder.EMPTY_DISCONNECT_MAX)
    checks.append((okc and vc == recorder.EMPTY_DISCONNECT_MAX,
                   "empty-timeout at the cap is accepted"))
    neg_ok, _ = recorder.parse_empty_timeout(-1)
    checks.append((not neg_ok, "empty-timeout rejects a negative value"))
    over_ok, _ = recorder.parse_empty_timeout(
        recorder.EMPTY_DISCONNECT_MAX + 1)
    checks.append((not over_ok, "empty-timeout rejects an over-cap value"))
    junk_ok, _ = recorder.parse_empty_timeout("soon")
    checks.append((not junk_ok, "empty-timeout rejects a non-number"))

    # Feature: empty_disconnect_seconds precedence (persisted > env > 60).
    saved_settings_path = recorder.SETTINGS_PATH
    saved_env = os.environ.pop("EMPTY_DISCONNECT_SECONDS", None)
    try:
        recorder.SETTINGS_PATH = sdir / "timeout-none.json"
        checks.append((recorder.empty_disconnect_seconds()
                       == recorder.EMPTY_DISCONNECT_DEFAULT,
                       "empty timeout falls back to the 60s default"))
        os.environ["EMPTY_DISCONNECT_SECONDS"] = "90"
        checks.append((recorder.empty_disconnect_seconds() == 90,
                       "empty timeout reads the env fallback when unset"))
        recorder.SETTINGS_PATH = sdir / "timeout-zero.json"
        recorder.save_settings({"empty_disconnect_seconds": 0},
                               path=recorder.SETTINGS_PATH)
        checks.append((recorder.empty_disconnect_seconds() == 0,
                       "a persisted 0 wins over the env (auto-stop off)"))
    finally:
        recorder.SETTINGS_PATH = saved_settings_path
        os.environ.pop("EMPTY_DISCONNECT_SECONDS", None)
        if saved_env is not None:
            os.environ["EMPTY_DISCONNECT_SECONDS"] = saved_env

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
