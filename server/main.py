"""FastAPI mixer: rooms of participants, one bidirectional socket each.

Each room's 50 Hz clock mixes its participants and fans the result out;
text frames carry JSON control, binary frames carry audio.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

from mixer import AudioMixer, MixSession, RoomNotFound

STATIC_DIR = Path(__file__).parent / "static"

# One registry; per-room sockets for control broadcasts; finished recordings
# by (room, id). Module-level by design; recordings are never evicted
# (known limit). Recording lookups skip room_exists on purpose: recordings
# outlive their room.
mixer = AudioMixer()
peers: dict[str, set[WebSocket]] = {}
recordings: dict[tuple[str, str], bytes] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for code in list(mixer.rooms):
        await mixer.close_room(code)


app = FastAPI(lifespan=lifespan)


async def broadcast_control(code: str, payload: dict) -> None:
    for sock in list(peers.get(code, ())):
        try:
            await sock.send_text(json.dumps(payload))
        except (WebSocketDisconnect, RuntimeError):
            pass  # that socket's own handler is tearing it down


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/rooms")
async def create_room() -> dict:
    return {"room_code": await mixer.create_room()}


@app.get("/api/rooms/{code}")
async def room_info(code: str) -> dict:
    if not mixer.room_exists(code):
        raise HTTPException(status_code=404, detail="unknown room code")
    return {"exists": True}


@app.get("/api/rooms/{code}/recordings/{recording_id}")
async def recording(code: str, recording_id: str) -> Response:
    wav = recordings.get((code.upper(), recording_id))
    if wav is None:
        raise HTTPException(status_code=404, detail="unknown recording")
    return Response(content=wav, media_type="audio/wav")


async def _receive_audio(ws: WebSocket, session: MixSession,
                         code: str, device: str,
                         queue: "asyncio.Queue") -> None:
    logged = False
    while True:
        message = await ws.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000))
        if message.get("text") == "stats":
            await ws.send_text(json.dumps(
                {"event": "stats", "devices": session.stats(),
                 "dropped": session.dropped_frames(queue)}))
        elif message.get("text") == "record:start":
            session.start_recording(device)
        elif message.get("text") == "record:stop":
            recorder = session.stop_recording(device)
            if recorder is not None:
                recording_id = uuid4().hex
                recordings[(code, recording_id)] = recorder.to_wav()
                await ws.send_text(json.dumps(
                    {"event": "recording", "recording_id": recording_id}))
        elif message.get("bytes"):
            if not logged:
                print(f"room {code}: device={device}, "
                      f"first chunk is {len(message['bytes'])} bytes")
                logged = True
            session.push(device, message["bytes"])


async def _send_mix(ws: WebSocket, queue: asyncio.Queue) -> None:
    while True:
        await ws.send_bytes(await queue.get())


@app.websocket("/ws/room/{code}")
async def room_socket(ws: WebSocket, code: str, device: str) -> None:
    await ws.accept()
    try:
        session = mixer.get_room(code)
    except RoomNotFound:
        await ws.close(code=4404, reason="unknown room")
        return
    code = code.upper()
    session.add_participant(device)
    queue = session.subscribe()
    peers.setdefault(code, set()).add(ws)
    await broadcast_control(code, {"event": "join", "device": device,
                                   "participants": session.participants()})
    receive = asyncio.create_task(_receive_audio(ws, session, code, device, queue))
    send = asyncio.create_task(_send_mix(ws, queue))
    try:
        await asyncio.gather(receive, send)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        receive.cancel()
        send.cancel()
        session.unsubscribe(queue)
        session.stop_recording(device)  # an owner-less recording is unreachable
        peers.get(code, set()).discard(ws)
        if not peers.get(code):
            peers.pop(code, None)
        if mixer.room_exists(code):
            await mixer.leave_room(code, device)
        if mixer.room_exists(code):
            await broadcast_control(code, {"event": "leave", "device": device,
                                           "participants": session.participants()})
