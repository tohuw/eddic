"""dave_recv — make Discord voice RECEIVE work under DAVE (E2EE) in
py-cord 2.8.0 by monkey-patching its voice engine at import time.

py-cord 2.8.0 already drives a full davey DaveSession off the voice
gateway (opcodes 21-31, MLS external sender / proposals / commit /
welcome) for SENDING, and its receive path even contains a DAVE decrypt
attempt — but that path ships broken:

  1. `PacketDecryptor._decrypt_rtp_aead_xchacha20_poly1305_rtpsize`
     hard-slices `result[8:]` instead of using the parsed extension
     header offset, corrupting the E2EE frame fed to davey, and never
     strips RTP padding.
  2. `PacketDecryptor.decrypt_rtp` returns None (packet dropped) for
     every packet whenever the DAVE session is not ready (passthrough
     phase) — and when DAVE decrypt succeeds it strips the (already
     stripped) extension header a second time, out of the *decrypted
     opus*, corrupting it.
  3. `AudioReader.__init__` never wires the voice client into the sink
     (`# self.sink._client = client` is commented out), so
     `PacketDecoder._process_packet` hits `assert self.sink.client`
     and kills the packet-router thread on the first packet.
  4. `PacketRouter.run`'s finally-clause calls `stop_recording()`
     unconditionally, raising RecordingException noise on every stop.
  5. A raw/undecryptable frame reaching the Opus decoder raises
     OpusError and kills the packet-router thread (no PLC fallback).

The fixes below are adopted from py-cord's in-progress voice-receive
rework, PR #3159 (https://github.com/Pycord-Development/pycord/pull/3159,
Pycord-Development, MIT) — decrypt_rtp / aead+strip_padding hunks ported
verbatim-in-spirit — plus the sink wiring and thread-hardening that PR
also does. Nothing under site-packages is edited; import this module
before creating any voice connection.

Requires the `davey` package (Snazzah's Rust DAVE-on-OpenMLS bindings,
https://github.com/Snazzah/davey — PyPI name: davey).
"""

from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord.voice.utils.dependencies import HAS_DAVEY

if not HAS_DAVEY:
    raise RuntimeError(
        "dave_recv requires the 'davey' package (pip install davey / "
        "uv run --with davey); py-cord found no DAVE bindings"
    )

import davey
from discord.opus import OpusError, PacketDecoder
from discord.voice.packets.rtp import RTPPacket
from discord.voice.receive import reader as _reader
from discord.voice.receive import router as _router

_log = logging.getLogger(__name__)

_TESTED_VERSIONS = {"2.8.0"}


# -- 1. RTPPacket.strip_padding (new method, from PR #3159) -----------------

def _strip_padding(self: RTPPacket, payload: bytes) -> bytes:
    if not self.padding or not payload:
        return payload
    pad_len = payload[-1]
    if 0 < pad_len <= len(payload):
        return payload[:-pad_len]
    return payload


# -- 2. transport decrypt: use the real ext-header offset, strip padding ----

def _decrypt_rtp_aead_xchacha20_poly1305_rtpsize(
    self: _reader.PacketDecryptor, packet: RTPPacket
) -> bytes:
    packet.adjust_rtpsize()
    nonce = packet.nonce + b"\x00" * 20

    try:
        result = self.box.decrypt(
            packet.decrypted_data or packet.data,
            bytes(packet.header),
            nonce,
        )
    except Exception as exc:
        _log.error("Critical error at AEAD: %s", exc)
        raise _reader.CryptoError(exc)

    if packet.extended:
        offset = packet.update_extended_header(result)
        result = result[offset:]  # upstream 2.8.0 hard-sliced [8:] here

    return packet.strip_padding(result)


# -- 3. decrypt_rtp: transport decrypt, then DAVE E2EE decrypt (PR #3159) ---

def _decrypt_rtp(self: _reader.PacketDecryptor, packet: RTPPacket) -> bytes:
    state = self.client._connection
    dave = state.dave_session

    raw_payload = self._decryptor_rtp(packet)

    if dave is not None and dave.ready:
        uid = state.ssrc_user_map.get(packet.ssrc)
        if uid:
            try:
                raw_payload = dave.decrypt(
                    uid, davey.MediaType.audio, raw_payload
                )
            except ValueError:
                # e.g. UnencryptedWhenPassthroughDisabled — drop the
                # packet so the opus decoder does PLC/FEC instead of
                # decoding garbage.
                _log.debug(
                    "DAVE: decryption failed, dropping packet for PLC",
                    exc_info=True,
                )
                raw_payload = b""
        else:
            # SSRC -> user_id mapping not yet populated (race with
            # member connect); cannot E2EE-decrypt without the binding.
            raw_payload = b""
        packet.decrypted_data = raw_payload
    else:
        # session absent or in passthrough (pre-transition media is not
        # E2EE) — the transport-decrypted payload IS the opus frame.
        packet.decrypted_data = raw_payload

    return packet.decrypted_data or b""


# -- 4. wire the sink to the client (upstream left it commented out) --------

_orig_reader_init = _reader.AudioReader.__init__


def _reader_init(self, sink, client, *, after=None, start=False):
    if getattr(sink, "vc", None) is None:
        sink.vc = client  # Sink.client property reads self.vc
    _orig_reader_init(self, sink, client, after=after, start=start)


# -- 5. don't let the router thread die noisily on stop ---------------------

def _router_run(self: _router.PacketRouter) -> None:
    try:
        self._do_run()
    except Exception as exc:
        _log.exception("Error in %s loop", self)
        self.reader.error = exc
    finally:
        try:
            self.reader.client.stop_recording()
        except Exception:
            pass  # already stopped — upstream raises RecordingException
        self.waiter.clear()


# -- 6. opus PLC fallback so one bad frame can't kill the decode thread -----

_orig_decode_packet = PacketDecoder._decode_packet


def _decode_packet(self, packet):
    try:
        return _orig_decode_packet(self, packet)
    except OpusError:
        _log.warning(
            "Opus decode failed for packet seq=%s; substituting PLC",
            getattr(packet, "sequence", "?"),
        )
        try:
            pcm = self._decoder.decode(None, fec=False)
        except Exception:
            pcm = b""
        return packet, pcm


def _install() -> None:
    if getattr(discord, "_dave_recv_patched", False):
        return
    if discord.__version__ not in _TESTED_VERSIONS:
        _log.warning(
            "dave_recv was written against py-cord %s; found %s — "
            "patching anyway",
            "/".join(sorted(_TESTED_VERSIONS)),
            discord.__version__,
        )
    RTPPacket.strip_padding = _strip_padding
    _reader.PacketDecryptor._decrypt_rtp_aead_xchacha20_poly1305_rtpsize = (
        _decrypt_rtp_aead_xchacha20_poly1305_rtpsize
    )
    _reader.PacketDecryptor.decrypt_rtp = _decrypt_rtp
    _reader.AudioReader.__init__ = _reader_init
    _router.PacketRouter.run = _router_run
    PacketDecoder._decode_packet = _decode_packet
    discord._dave_recv_patched = True
    print(
        f"dave_recv: DAVE receive patches applied "
        f"(py-cord {discord.__version__}, davey {davey.__version__}, "
        f"proto {davey.DAVE_PROTOCOL_VERSION})"
    )


_install()


# -- unattended live self-test (temporary spike scaffolding) ----------------

async def selftest(bot, channel_id: int, sink=None, seconds: float = 20.0):
    """Connect to `channel_id`, verify the DAVE/MLS session establishes,
    run start_recording for `seconds`, report, and tear down. Enabled
    from the recorder capability when DAVE_SELFTEST_CHANNEL is set."""

    tag = "dave_recv selftest:"
    ok = True
    if os.environ.get("DAVE_SELFTEST_DEBUG"):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(name)s %(levelname)s %(message)s"))

        class _NoSecrets(logging.Filter):
            def filter(self, record):
                m = record.getMessage()
                return not any(s in m for s in
                               ("Identifying", "secret_key", "token"))

        handler.addFilter(_NoSecrets())
        for name in ("discord.voice.gateway", "discord.voice.state"):
            lg = logging.getLogger(name)
            lg.setLevel(logging.DEBUG)
            lg.addHandler(handler)
    try:
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(
            channel_id
        )
        print(f"{tag} connecting to voice channel {channel_id}")
        vc = await channel.connect()
        for _ in range(100):
            if vc.is_connected():
                break
            await asyncio.sleep(0.2)
        else:
            print(f"{tag} FAIL — voice never connected")
            return

        state = vc._connection
        last_status = None
        session = None
        for _ in range(100):
            session = state.dave_session
            if session is not None and session.status != last_status:
                last_status = session.status
                print(
                    f"{tag} dave status={session.status} "
                    f"ready={session.ready} epoch={session.epoch}"
                )
            if session is not None and session.ready:
                break
            await asyncio.sleep(0.2)

        print(
            f"{tag} dave_protocol_version={state.dave_protocol_version} "
            f"session={session!r}"
        )
        if session is not None and session.ready:
            print(
                f"{tag} MLS group established — epoch={session.epoch} "
                f"privacy_code={session.voice_privacy_code!r} "
                f"members={session.get_user_ids()}"
            )
        elif (
            session is not None
            and state.dave_protocol_version >= 1
            and session.status == davey.SessionStatus.pending
            and session.epoch == 0
        ):
            # Whitepaper-correct solo state: a lone member holds a
            # local *pending* group of one (external sender applied,
            # key package sent); the gateway only broadcasts the
            # establishing commit/welcome once a second member joins.
            print(
                f"{tag} DAVE handshake OK (solo-pending) — local MLS "
                f"group of one at epoch 0, members="
                f"{session.get_user_ids()}; establishment completes "
                f"when a human joins"
            )
        else:
            ok = False
            print(f"{tag} FAIL — DAVE session in unexpected state")

        if sink is None:
            class _ProbeSink(discord.sinks.Sink):
                __sink_listeners__ = []

                def __init__(self):
                    super().__init__()
                    self.count = 0

                def is_opus(self):
                    return False

                def walk_children(self):
                    return []

                def write(self, data, user):
                    self.count += 1

                def cleanup(self):
                    pass

            sink = _ProbeSink()

        def finished(exc):
            print(f"{tag} recorder finished callback, exc={exc!r}")

        vc.start_recording(sink, finished)
        print(f"{tag} start_recording OK; listening {seconds:.0f}s")
        await asyncio.sleep(seconds)

        reader = vc._reader
        if reader:
            if reader.error is not None:
                ok = False
                print(f"{tag} FAIL — reader.error={reader.error!r}")
            if not reader.packet_router.is_alive():
                ok = False
                print(f"{tag} FAIL — packet router thread died")
            if not reader.event_router.is_alive():
                ok = False
                print(f"{tag} FAIL — event router thread died")
        else:
            ok = False
            print(f"{tag} FAIL — reader gone before stop")

        vc.stop_recording()
        await vc.disconnect()
        print(f"{tag} {'PASS' if ok else 'FAIL'} — "
              f"listened {seconds:.0f}s, teardown clean")
    except Exception as exc:
        print(f"{tag} FAIL — unhandled: {exc!r}")
        raise
