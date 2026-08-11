"""Accumulates the mixed stream for one recording; complete by design."""
import time

from mixer.wav import encode_wav


class Recorder:
    """Grows without bound by design: a recording must be complete, so
    frames are never dropped and there is no length cap."""

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.audio = bytearray()
        self.started_at = time.time()

    def append(self, frame_bytes: bytes) -> None:
        self.audio.extend(frame_bytes)

    def to_wav(self) -> bytes:
        return encode_wav(bytes(self.audio))
