"""Pure audio mixing functions. No state, no I/O."""
from typing import Iterator

import numpy as np

from mixer.constants import BYTES_PER_FRAME, DTYPE, SAMPLES_PER_FRAME


def iter_frames(audio: bytes) -> Iterator[np.ndarray]:
    """Yield fixed-size int16 frames, zero-padding the final partial frame."""
    for start in range(0, len(audio), BYTES_PER_FRAME):
        frame = np.frombuffer(audio[start:start + BYTES_PER_FRAME], dtype=DTYPE)
        if len(frame) < SAMPLES_PER_FRAME:
            frame = np.pad(frame, (0, SAMPLES_PER_FRAME - len(frame))) # Pad with zeros to ensure the frame is the correct size
        yield frame


def mix_frames(frames: list[np.ndarray]) -> np.ndarray:
    """Sum frames with int32 headroom, clip to the int16 range, return int16."""
    if not frames:
        return np.zeros(SAMPLES_PER_FRAME, dtype=DTYPE) # Return silence if no frames are provided
    total = np.sum(np.stack(frames).astype(np.int32), axis=0) # Sum the frames with int32 to avoid overflow
    info = np.iinfo(np.int16)
    return np.clip(total, info.min, info.max).astype(DTYPE) 


def mix_streams(streams: list[bytes]) -> bytes:
    """Mix audio byte streams frame by frame.

    Shorter streams contribute silence once exhausted; the output length
    matches the longest input, so frame padding never leaks into the result.
    """
    out_len = max(map(len, streams), default=0) # Determine the length of the longest stream
    n_frames = -(-out_len // BYTES_PER_FRAME) 
    iterators = [iter_frames(s) for s in streams]
    out = bytearray()
    for _ in range(n_frames):
        frames = [f for f in (next(it, None) for it in iterators) if f is not None]
        out += mix_frames(frames).tobytes()
    return bytes(out[:out_len])
