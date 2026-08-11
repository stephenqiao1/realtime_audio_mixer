"""FastAPI relay: publishers send raw audio chunks, monitors receive them.

No mixing yet -- every publisher chunk is forwarded unchanged to every monitor.
"""
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"

# Connected monitor sockets. Module-level by design for this iteration.
monitors: list[WebSocket] = []


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
            if not logged:
                print(f"publish: device={device}, first chunk is {len(chunk)} bytes")
                logged = True
            for sock in list(monitors):
                try:
                    await sock.send_bytes(chunk)
                except RuntimeError:
                    # Monitor disconnected mid-send; drop it here since its own
                    # handler may still be blocked in receive.
                    if sock in monitors:
                        monitors.remove(sock)
    except WebSocketDisconnect:
        pass


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
