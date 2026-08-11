# Realtime Audio Mixer

First iteration: offline mixing of 16 kHz mono 16-bit audio WAV files.

## Install

```
pip install -e "core[dev]"
```

## Run tests

```
pytest core/tests
```

## Mix two WAV files

```
python examples/mix_files.py input1.wav input2.wav output.wav
```

## Run the server

```
pip install fastapi "uvicorn[standard]"
uvicorn server.main:app
```

Then open <http://localhost:8000/> in each participant's browser: create a
room in one tab and join it from the others with its 4-character code
(works across machines on one network; name a tab with `?device=alice`).
Everyone in a room hears the live mix; the Record button captures it and
plays it back on the page. Wear headphones.

## Known limitations

Recordings are held in server memory and never evicted; restarting the
server clears them. Everything runs in one process. The mix you hear
includes your own voice (no per-participant mix-minus yet).
