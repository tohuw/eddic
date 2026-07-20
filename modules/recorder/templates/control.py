"""Muninn control surface — a loopback-only HTTP control server that
lets a local tool (an Elgato Stream Deck, a hotkey, a curl in a script)
start/stop recording and read status, mapping to exactly the same
actions as the `/record` slash commands.

Bound to 127.0.0.1 only — it is a control channel for the machine the
recorder already runs on, never exposed to the network. An optional
shared-secret header (`X-Muninn-Token`) guards it against other local
processes when the owner sets CONTROL_TOKEN.

The socket layer is a thin shell over `route()`, a pure function that
does auth + method/path dispatch and returns (status_code, body_dict).
That purity is deliberate: the whole request contract is unit-testable
with no network and no Discord — see the module verifier.

Endpoints:
    GET  /            -> status (alias of /status)
    GET  /status      -> {"ok", "recording", "sessions": [...]}
    GET  /healthz     -> liveness, no auth needed
    POST /record/start (alias /start) -> begin recording
    POST /record/stop  (alias /stop)  -> stop recording

Actions are injected as zero-arg callables returning a dict with an
"ok" key; the server maps ok->200 and not-ok->409 (a conflict such as
"already recording" / "nothing to stop"), status always 200.
"""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN_HEADER = "X-Muninn-Token"


def route(method, path, token, *, expected_token, actions):
    """Pure request router. `actions` maps "start"/"stop"/"status" to
    zero-arg callables each returning a result dict. Returns
    (status_code, body_dict). No sockets, no Discord — pure and
    unit-testable."""
    p = path.split("?", 1)[0].rstrip("/") or "/"
    # Liveness never needs the secret: it proves the port is Muninn's
    # without doing anything and lets a button show reachable/unreachable.
    if method == "GET" and p == "/healthz":
        return 200, {"ok": True, "service": "muninn-control"}
    if expected_token and token != expected_token:
        return 401, {"ok": False, "error": "unauthorized"}
    if method == "GET" and p in ("/", "/status"):
        body = actions["status"]()
        return 200, body
    if method == "POST" and p in ("/record/start", "/start"):
        body = actions["start"]()
        return (200 if body.get("ok") else 409), body
    if method == "POST" and p in ("/record/stop", "/stop"):
        body = actions["stop"]()
        return (200 if body.get("ok") else 409), body
    return 404, {"ok": False, "error": "not found", "path": p}


def _make_handler(actions, expected_token):
    class Handler(BaseHTTPRequestHandler):
        server_version = "MuninnControl/1.0"

        def _dispatch(self):
            token = self.headers.get(TOKEN_HEADER)
            try:
                code, body = route(self.command, self.path, token,
                                   expected_token=expected_token,
                                   actions=actions)
            except Exception as e:  # never leak a stack to the client
                code, body = 500, {"ok": False,
                                   "error": f"{type(e).__name__}: {e}"}
            payload = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

        def log_message(self, *args):
            pass  # the recorder owns stdout; stay quiet

    return Handler


def start_control_server(loop, *, open_session, close_session, status,
                         resolve_target, host="127.0.0.1", port=8776,
                         token=None):
    """Start the loopback control server on its own daemon thread.

    `open_session(guild_id, channel)` and `close_session()` are
    coroutine factories run on the recorder's event `loop` via
    run_coroutine_threadsafe (Discord work must happen there, not on the
    HTTP thread). `resolve_target()` is a coroutine returning
    (guild_id, channel) or an error dict — it chooses what to record
    when no slash context named a channel. `status()` is a pure,
    thread-safe snapshot. Returns the HTTPServer (call .shutdown())."""

    def _run(coro, timeout=45):
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        return fut.result(timeout)

    def do_start():
        try:
            target = _run(resolve_target())
            if isinstance(target, dict):   # resolution failed
                return target
            guild_id, channel = target
            return _run(open_session(guild_id, channel))
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def do_stop():
        try:
            return _run(close_session())
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    actions = {"start": do_start, "stop": do_stop, "status": status}
    handler = _make_handler(actions, token)
    httpd = ThreadingHTTPServer((host, port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True,
                         name="muninn-control")
    t.start()
    return httpd
