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

Then open:

- <http://localhost:8000/?mode=publish> — captures your microphone (name a tab with `&device=alice`); the Record button captures the mixed stream and plays it back on the page
- <http://localhost:8000/?mode=monitor> — plays whatever publishers are sending

## Known limitations

Recordings are held in server memory and never evicted; restarting the
server clears them. Everything is one process and one shared room.
