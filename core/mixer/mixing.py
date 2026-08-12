"""Pure mixing math: sum with int32 headroom, clip to int16. No state, no I/O."""
import numpy as np

from mixer.constants import DTYPE, SAMPLES_PER_FRAME


def mix_frames(frames: list[np.ndarray]) -> np.ndarray:
    """Sum frames with int32 headroom, clip to the int16 range, return int16."""
    if not frames:
        return np.zeros(SAMPLES_PER_FRAME, dtype=DTYPE)
    total = np.sum(np.stack(frames).astype(np.int32), axis=0)
    info = np.iinfo(np.int16)
    return np.clip(total, info.min, info.max).astype(DTYPE)
