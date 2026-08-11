"""FastAPI mixer: publishers fill per-device slots; the session's 50 Hz
clock mixes them; monitors drain subscriber queues; recordings of the mix
are kept in memory and served for download."""
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

from mixer import MixSession

STATIC_DIR = Path(__file__).parent / "static"

# The one mixing session, and finished recordings by id. Module-level by
# design for this iteration; recordings are never evicted (known limit).
session = MixSession()
recordings: dict[str, bytes] = {}  # id -> wav bytes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await session.start()
    yield
    await session.close()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/recording/{recording_id}")
async def recording(recording_id: str) -> Response:
    if recording_id not in recordings:
        raise HTTPException(status_code=404, detail="unknown recording id")
    # Served inline: the page plays recordings back, downloads are not a feature.
    return Response(content=recordings[recording_id], media_type="audio/wav")


@app.websocket("/ws/publish")
async def publish(ws: WebSocket, device: str) -> None:
    await ws.accept()
    session.add_participant(device)
    logged = False
    try:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text") == "record:start":
                session.start_recording(device)
            elif message.get("text") == "record:stop":
                recorder = session.stop_recording(device)
                if recorder is not None:
                    recording_id = uuid4().hex
                    recordings[recording_id] = recorder.to_wav()
                    # The only text a publisher ever receives: a finished id.
                    await ws.send_text(recording_id)
            elif message.get("bytes"):
                if not logged:
                    print(f"publish: device={device}, "
                          f"first chunk is {len(message['bytes'])} bytes")
                    logged = True
                session.push(device, message["bytes"])
    finally:
        # A recording whose owner vanished has no way to deliver its id.
        session.stop_recording(device)
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
