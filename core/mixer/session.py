"""Per-participant session state and the frame clock. No I/O."""
import asyncio
import time

import numpy as np

from mixer.constants import BYTES_PER_FRAME, DTYPE, FRAME_MS
from mixer.mixing import mix_frames

# A frame of all zeroes is silence: what a participant contributes on
# any tick where no fresh audio arrived from them.
SILENCE = bytes(BYTES_PER_FRAME)

# One second of frames. A subscriber further behind than this is not
# listening in any useful sense, so the bound also caps how stale any
# delivered frame can be.
QUEUE_MAX_FRAMES = 1000 // FRAME_MS


class MixSession:
    """Stores each device's latest frame; a clock mixes at 50 Hz and fans
    the result out to subscriber queues without ever blocking on one."""

    def __init__(self) -> None:
        self._latest: dict[str, bytes | None] = {}
        self._subscribers: dict[asyncio.Queue, int] = {}  # queue -> frames dropped
        self._task: asyncio.Task | None = None

    def add_participant(self, device_id: str) -> None:
        self._latest.setdefault(device_id, None)

    def remove_participant(self, device_id: str) -> None:
        self._latest.pop(device_id, None)

    def push(self, device_id: str, audio: bytes) -> None:
        self._latest[device_id] = audio

    def participants(self) -> list[str]:
        return list(self._latest)

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
            for device_id, slot in self._latest.items():
                # Clearing after the read is what makes a device that stopped
                # sending contribute silence instead of its stale last frame.
                frames.append(np.frombuffer(slot or SILENCE, dtype=DTYPE))
                self._latest[device_id] = None
            self._publish(mix_frames(frames).tobytes())
            deadline += period
