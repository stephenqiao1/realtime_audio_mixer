# Realtime Audio Mixer

Rooms of devices stream 16 kHz mono 16-bit audio over WebSockets; each
room's 50 Hz clock mixes its participants into one unified stream for
live monitoring, playback and recording.

## Run everything

```
./run.sh
```

Creates a local virtualenv, installs the core package and server
dependencies, runs the test suite, and starts the server on port 8000
(pick another with `PORT=8001 ./run.sh`). macOS and Linux; on Windows,
run it inside WSL or follow Manual setup.

Then open <http://localhost:8000/> in each participant's browser: create a
room in one tab and join it from the others with its 4-character code.
Other devices on your network can join at your machine's LAN address
(printed by the script). Everyone in a room hears the live mix; the
Record button captures it, listed on the page with playback and download.
Wear headphones.

Browsers allow microphone capture only on HTTPS or localhost. A phone on
the LAN loads the page over plain HTTP, so its mic is blocked — pick the
"Test file" audio source instead (it works over plain HTTP), or front the
server with a tunnel or a self-signed certificate. The test-file source
also lets two tabs on one machine demo a two-speaker conversation, since
they would otherwise share the same microphone: two generated sample
voices ship with the page (speaker_a / speaker_b — each pauses where the
other talks), or pick any WAV — it is resampled on decode.

## Manual setup

```
pip install -e "core[dev]" fastapi "uvicorn[standard]"
pytest core/tests
uvicorn server.main:app --host 0.0.0.0
```

## Using the core as a library

The mixing engine is a standalone Python package (numpy is its only
dependency) — the server above is just one transport wrapped around it.

```
pip install "git+https://github.com/stephenqiao1/realtime_audio_mixer.git#subdirectory=core"
```

(or from a checkout: `pip install path/to/core`)

Create a room, push audio in, subscribe to the mix:

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

Jitter buffering, the fixed-rate output clock, silence substitution for
stalled devices and per-room isolation all happen behind `push()` and
`subscribe()`. For a complete capture rather than a live stream, use
`room.start_recording(device)` and `room.stop_recording(device).to_wav()`
— recordings never drop frames, while subscriber queues drop for
consumers that fall more than a second behind, because live audio must
not back up (`room.stats()` and `room.dropped_frames(queue)` expose
both sides).

Two rules bind the caller: audio is 16 kHz mono 16-bit int16
(`mixer.constants` is the contract), and all calls belong to one asyncio
event loop — the core uses no threads and no locks. To integrate from
another language, run the server as a sidecar and speak its WebSocket
protocol instead; `server/main.py` is the reference for wrapping the
core in any transport.

## Known limitations

Recordings are held in server memory and never evicted; restarting the
server clears them. Everything runs in one process. The mix you hear
includes your own voice (no per-participant mix-minus yet).
