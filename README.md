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

- <http://localhost:8000/?mode=publish> — sends a test tone (pick a pitch with `&freq=660`)
- <http://localhost:8000/?mode=monitor> — plays whatever publishers are sending
