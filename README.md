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

## Known limitations

Recordings are held in server memory and never evicted; restarting the
server clears them. Everything runs in one process. The mix you hear
includes your own voice (no per-participant mix-minus yet).
