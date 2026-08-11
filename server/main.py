"""FastAPI mixer: the latest chunk from each publisher is mixed and broadcast.

Mixing happens synchronously on every chunk arrival -- no server clock yet.
"""
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from mixer import MixSession
from mixer.constants import BYTES_PER_FRAME

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"

# Connected monitor sockets and the one mixing session.
# Module-level by design for this iteration.
monitors: list[WebSocket] = []
session = MixSession()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws/publish")
async def publish(ws: WebSocket, device: str) -> None:
    await ws.accept()
    session.add_participant(device)
    logged = False
    try:
        while True:
            chunk = await ws.receive_bytes()
            if len(chunk) != BYTES_PER_FRAME:
                continue  # the mix stacks whole frames; drop anything else
            if not logged:
                print(f"publish: device={device}, first chunk is {len(chunk)} bytes")
                logged = True
            mixed = session.push(device, chunk)
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
        session.remove_participant(device)


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
