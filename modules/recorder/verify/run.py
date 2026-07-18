# /// script
# requires-python = ">=3.9"
# ///
"""Verify the recorder's consent core without discord or davey
installed: both templates compile; with a stubbed library, emoji
normalization accepts reacts with and without the variation
selector, the sink drops unattributed and unconsented packets while
counting them, consented audio lands as a well-formed per-speaker
WAV, and revocation closes the gate mid-stream."""

import os
import py_compile
import sys
import tempfile
import types
import wave
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def main():
    checks = []
    for name in ("recorder.py", "dave_recv.py"):
        try:
            py_compile.compile(str(TEMPLATES / name), doraise=True)
            checks.append((True, f"{name} compiles"))
        except py_compile.PyCompileError as e:
            checks.append((False, f"{name} compile error: {e}"))

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

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print("verify ok: recorder module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
