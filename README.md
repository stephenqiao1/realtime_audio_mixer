# Realtime Audio Mixer

Rooms of devices stream 16 kHz mono 16-bit audio over WebSockets; each
room's 50 Hz clock mixes them into one unified stream for live
monitoring, playback and recording.

## Architecture

```text
┌──────────────┐  ┌──────────────┐  ┌──────────────┐     the test simulator: each
│   device A   │  │   device B   │  │   device N   │     participant streams a mic,
│  (browser)   │  │  (browser)   │  │  (browser)   │     local WAV, or bundled sample
└───────┬──────┘  └───────┬──────┘  └───────┬──────┘     voice, and hears the live mix
        └─────────────────┼─────────────────┘
                          │  one WebSocket per participant
                          ▼
┌───────────────────────────────────────────────────────────────────────┐
│ server/main.py — transport layer: moves bytes and JSON, no audio      │
│ logic in this file                                                    │
│   WS   /ws/room/{code}   receive loop → push() · send loop ← queue    │
│   HTTP create/check rooms · serve recordings · sample voices · page   │
└─────────────────────────────┬─────────────────────────────────────────┘
                              │  direct python calls
┌─────────────────────────────▼─────────────────────────────────────────┐
│ core/mixer — pip-installable library · no I/O · numpy only            │
│                                                                       │
│   AudioMixer ── 4-char room code ──► MixSession (one per room)        │
│                                                                       │
│   push(device, bytes)                                                 │
│     └─► byte accumulator ──► JitterBuffer per device                  │
│                              (primes at 60 ms, bounded at 200 ms)     │
│   50 Hz clock, absolute deadlines                                     │
│     └─► pop every buffer ──► mix_frames(): sum in int32, clip         │
│            │                                                          │
│            ├─► subscriber queues — bounded, drop-oldest (live)        │
│            └─► recorders — never drop, complete ──► WAV bytes         │
│                                                                       │
│   built on: mixing.py (pure math) · constants.py (the 16 kHz mono     │
│   16-bit / 20 ms contract) · wav.py (in-memory WAV encoding)          │
└───────────────────────────────────────────────────────────────────────┘
```

Three rules hold the design together:

- Mixing state lives in the core; all I/O lives outside it.
- The clock decides when output exists — never input arrival.
- Consumers are live (bounded queue, may drop) or recordings
  (unbounded, never drop). Nothing in between.

## Quick start

```
./run.sh
```

Creates a venv, installs dependencies, runs the tests, starts the
server. macOS/Linux; on Windows use WSL or the manual setup.

- Different port: `PORT=8001 ./run.sh`
- Other devices on your network: use the LAN address the script prints

## Demo

1. Open <http://localhost:8000/> in two tabs.
2. Tab 1: **Create room**. Tab 2: type the code, **Join**.
3. In each tab pick source **Test file**, then a different sample
   voice. You hear both speakers mixed live.
4. **Record** captures the mix; it appears under Recordings with
   playback and download.

Microphone instead: browsers allow it only on HTTPS or localhost, so
phones on plain-HTTP LAN must use the Test file source. Wear
headphones — the mix includes your own voice.

## Manual setup

```
pip install -e "core[dev]" fastapi "uvicorn[standard]"
pytest core/tests
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000/>. Port taken? Pick another with `--port`.

## Using the core as a library

The engine is a standalone package (numpy only); the server is just one
transport around it.

```
pip install "git+https://github.com/stephenqiao1/realtime_audio_mixer.git#subdirectory=core"
```

```python
import asyncio
from mixer import AudioMixer

async def main():
    mixer = AudioMixer()
    code = await mixer.create_room()    # starts the room's 50 Hz clock
    room = mixer.get_room(code)

    room.add_participant("device-a")
    room.push("device-a", audio_bytes)  # 16 kHz mono 16-bit, any chunk size

    queue = room.subscribe()
    mixed_frame = await queue.get()     # one 640-byte frame every 20 ms

    await mixer.close_room(code)

asyncio.run(main())
```

- Jitter buffering, the fixed-rate clock, silence for stalled devices
  and room isolation all happen behind `push()` and `subscribe()`.
- Live queues drop when a consumer falls a second behind; recordings
  (`start_recording` / `stop_recording(...).to_wav()`) never drop.
  `room.stats()` and `room.dropped_frames(queue)` expose both.
- Two rules: audio is 16 kHz mono int16 (`mixer.constants` is the
  contract), and everything runs on one asyncio event loop.
- From other languages: run the server as a sidecar and speak its
  WebSocket protocol; `server/main.py` is the reference transport.

## Known limitations

Recordings live in server memory (cleared on restart), everything runs
in one process, and the mix includes your own voice — no
per-participant mix-minus yet.
