"""Per-device jitter cushion: trades a little fixed latency for smooth audio."""
from collections import deque

from mixer.constants import BYTES_PER_FRAME

SILENCE = bytes(BYTES_PER_FRAME)


class JitterBuffer:
    """FIFO of whole frames. pop() never blocks and never raises: an empty
    buffer yields silence. Bounded: overflow discards the oldest frame,
    because in real time the newest audio is always the most valuable."""

    def __init__(self, target_depth: int = 3, max_depth: int = 10) -> None:
        self._frames: deque[bytes] = deque()
        self._target_depth = target_depth
        self._max_depth = max_depth
        self._primed = False
        self.underruns = 0
        self.overruns = 0

    def push(self, frame: bytes) -> None:
        self._frames.append(frame)
        if len(self._frames) > self._max_depth:
            self._frames.popleft()
            self.overruns += 1

    def pop(self) -> bytes:
        if not self._frames:
            self.underruns += 1
            return SILENCE
        return self._frames.popleft()

    @property
    def depth(self) -> int:
        return len(self._frames)

    def prime(self) -> bool:
        # Sticky: once the cushion has built up, the device stays eligible;
        # later starvation surfaces as underruns, not re-gating.
        if len(self._frames) >= self._target_depth:
            self._primed = True
        return self._primed
