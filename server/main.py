"""FastAPI mixer: publishers fill per-device slots; the session's 50 Hz
clock mixes them; each monitor drains its own subscriber queue."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from mixer import MixSession
from mixer.constants import BYTES_PER_FRAME

STATIC_DIR = Path(__file__).parent / "static"

# The one mixing session. Module-level by design for this iteration.
session = MixSession()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await session.start()
    yield
    await session.close()


app = FastAPI(lifespan=lifespan)


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
            session.push(device, chunk)
    except WebSocketDisconnect:
        pass
    finally:
        session.remove_participant(device)


@app.websocket("/ws/monitor")
async def monitor(ws: WebSocket) -> None:
    await ws.accept()
    queue = session.subscribe()
    try:
        while True:
            await ws.send_bytes(await queue.get())
    except (WebSocketDisconnect, RuntimeError):
        # The clock always emits, so a dead socket fails a send within
        # one tick; that failure is our disconnect signal now that the
        # handler no longer sits in receive.
        pass
    finally:
        session.unsubscribe(queue)
