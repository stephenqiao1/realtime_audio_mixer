"""One room's live mixing engine: push() audio in, subscribe() to the mix."""
import asyncio
import time

import numpy as np

from mixer.buffer import JitterBuffer
from mixer.recorder import Recorder
from mixer.constants import BYTES_PER_FRAME, DTYPE, FRAME_MS
from mixer.mixing import mix_frames

# One second of frames. A subscriber further behind than this is not
# listening in any useful sense, so the bound also caps how stale any
# delivered frame can be.
QUEUE_MAX_FRAMES = 1000 // FRAME_MS


class MixSession:
    """Buffers each device's incoming audio; a clock mixes at 50 Hz and fans
    the result out to subscriber queues without ever blocking on one."""

    def __init__(self, target_depth: int = 3, max_depth: int = 10) -> None:
        self._buffers: dict[str, JitterBuffer] = {}
        self._pending: dict[str, bytes] = {}  # device -> partial-frame bytes
        self._target_depth = target_depth
        self._max_depth = max_depth
        self._subscribers: dict[asyncio.Queue, int] = {}  # queue -> frames dropped
        self._recorders: dict[str, Recorder] = {}  # device -> active recording
        self._task: asyncio.Task | None = None

    def add_participant(self, device_id: str) -> None:
        self._buffers.setdefault(
            device_id, JitterBuffer(self._target_depth, self._max_depth))
        self._pending.setdefault(device_id, b"")

    def remove_participant(self, device_id: str) -> None:
        self._buffers.pop(device_id, None)
        self._pending.pop(device_id, None)

    def push(self, device_id: str, audio: bytes) -> None:
        if device_id not in self._buffers:
            self.add_participant(device_id)
        data = self._pending[device_id] + audio
        while len(data) >= BYTES_PER_FRAME:
            self._buffers[device_id].push(data[:BYTES_PER_FRAME])
            data = data[BYTES_PER_FRAME:]
        self._pending[device_id] = data

    def participants(self) -> list[str]:
        return list(self._buffers)

    def stats(self) -> dict[str, dict[str, int]]:
        return {device: {"depth": buffer.depth,
                         "underruns": buffer.underruns,
                         "overruns": buffer.overruns}
                for device, buffer in self._buffers.items()}

    def start_recording(self, device_id: str) -> None:
        # Starting over an unfinished recording abandons it: a new
        # recording is always a fresh Recorder, never a resume.
        self._recorders[device_id] = Recorder(device_id)

    def stop_recording(self, device_id: str) -> Recorder | None:
        return self._recorders.pop(device_id, None)

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=QUEUE_MAX_FRAMES)
        self._subscribers[queue] = 0
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.pop(queue, None)

    def dropped_frames(self, queue: asyncio.Queue) -> int:
        return self._subscribers.get(queue, 0)

    def _publish(self, mixed: bytes) -> None:
        for queue in self._subscribers:
            try:
                queue.put_nowait(mixed)
            except asyncio.QueueFull:
                # Late audio is worthless in real time: sacrifice this
                # subscriber's oldest frame, never block the clock. Only
                # this subscriber loses data.
                queue.get_nowait()
                queue.put_nowait(mixed)
                self._subscribers[queue] += 1

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        period = FRAME_MS / 1000
        deadline = time.perf_counter() + period
        while True:
            delay = deadline - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                # Fell behind (suspended machine, slow tick): resync to
                # now instead of firing a burst of catch-up ticks.
                deadline = time.perf_counter()
            frames = []
            for buffer in self._buffers.values():
                # An unprimed newcomer sits out until its cushion builds,
                # so it starts smooth instead of underrunning immediately.
                if buffer.prime():
                    frames.append(np.frombuffer(buffer.pop(), dtype=DTYPE))
            mixed = mix_frames(frames).tobytes()
            for recorder in self._recorders.values():
                # Synchronous and unbounded on purpose: recordings must be
                # complete, unlike live playback which may drop.
                recorder.append(mixed)
            self._publish(mixed)
            deadline += period
