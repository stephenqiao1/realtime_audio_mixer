"""Per-participant session state. Synchronous, no I/O."""
import numpy as np

from mixer.constants import BYTES_PER_FRAME, DTYPE
from mixer.mixing import mix_frames

# A slot holding all zeroes is silence, so a participant that has not
# pushed yet contributes nothing to the mix.
SILENCE = bytes(BYTES_PER_FRAME)


class MixSession:
    """Tracks each device's latest frame and mixes all slots on push."""

    def __init__(self) -> None:
        self._latest: dict[str, bytes] = {}

    def add_participant(self, device_id: str) -> None:
        self._latest.setdefault(device_id, SILENCE)

    def remove_participant(self, device_id: str) -> None:
        self._latest.pop(device_id, None)

    def push(self, device_id: str, audio: bytes) -> bytes:
        self._latest[device_id] = audio
        frames = [np.frombuffer(a, dtype=DTYPE) for a in self._latest.values()]
        return mix_frames(frames).tobytes()

    def participants(self) -> list[str]:
        return list(self._latest)
