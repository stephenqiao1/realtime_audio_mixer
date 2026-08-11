"""FastAPI mixer: the latest chunk from each publisher is mixed and broadcast.

Mixing happens synchronously on every chunk arrival -- no server clock yet.
"""
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from mixer.constants import BYTES_PER_FRAME, DTYPE
from mixer.mixing import mix_frames

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"

# Connected monitor sockets and each publisher's most recent chunk.
# Module-level by design for this iteration.
monitors: list[WebSocket] = []
latest: dict[str, bytes] = {}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws/publish")
async def publish(ws: WebSocket, device: str) -> None:
    await ws.accept()
    logged = False
    try:
        while True:
            chunk = await ws.receive_bytes()
            if len(chunk) != BYTES_PER_FRAME:
                continue  # mix_frames stacks whole frames; drop anything else
            if not logged:
                print(f"publish: device={device}, first chunk is {len(chunk)} bytes")
                logged = True
            latest[device] = chunk
            frames = [np.frombuffer(c, dtype=DTYPE) for c in latest.values()]
            mixed = mix_frames(frames).tobytes()
            for sock in list(monitors):
                try:
                    await sock.send_bytes(mixed)
                except RuntimeError:
                    # Monitor disconnected mid-send; drop it here since its own
                    # handler may still be blocked in receive.
                    if sock in monitors:
                        monitors.remove(sock)
    except WebSocketDisconnect:
        pass
    finally:
        latest.pop(device, None)


@app.websocket("/ws/monitor")
async def monitor(ws: WebSocket) -> None:
    await ws.accept()
    monitors.append(ws)
    try:
        while True:
            # Monitors never send data; this only waits for the disconnect.
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in monitors:
            monitors.remove(ws)
