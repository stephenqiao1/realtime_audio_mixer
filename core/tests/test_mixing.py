"""Pure mixing math: summing, clipping, silence identity, the empty mix."""
import numpy as np

from mixer.constants import BYTES_PER_FRAME, DTYPE, SAMPLE_RATE, SAMPLES_PER_FRAME
from mixer.mixing import mix_frames


def sine_frame(amplitude, freq=440.0): # Generate one 20 ms sine frame with the given amplitude and frequency.
    t = np.arange(SAMPLES_PER_FRAME) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(DTYPE)


def test_two_tones_sum_without_wraparound(): # Test that mixing two tones of moderate amplitude does not cause wraparound in the int16 range.
    """Two in-phase tones at amplitude 8000 must sum to ~16000: well inside
    int16, so the mix has to be the plain sample-wise sum. A signed overflow
    would betray itself as a large negative minimum.
    """
    tone = sine_frame(8000)
    mixed = mix_frames([tone, tone])
    assert 15900 <= mixed.max() <= 16000
    assert mixed.min() >= -16000  # a wraparound would show up near -32768


def test_loud_tones_clamp_at_int16_range(): # Test that mixing two loud tones clamps the output to the int16 range.
    """Two tones at 30000 sum far past int16. The mix must saturate at the
    range edges (clip), never wrap around into noise.
    """
    tone = sine_frame(30000)
    mixed = mix_frames([tone, tone])
    assert mixed.max() == 32767
    assert mixed.min() == -32768


def test_mixing_with_silence_is_identity(): # Test that mixing a tone with silence returns the original tone.
    """All-zero samples add nothing, so mixing with a silent frame must
    return the other frame unchanged.
    """
    tone = sine_frame(8000)
    silence = np.zeros(SAMPLES_PER_FRAME, dtype=DTYPE)
    assert np.array_equal(mix_frames([tone, silence]), tone)


def test_empty_mix_is_one_silent_frame():
    """The clock mixes whatever is primed -- sometimes nothing. An empty
    input must yield a whole frame of silence, never an error: this is
    what monitors hear while a room is quiet.
    """
    assert mix_frames([]).tobytes() == bytes(BYTES_PER_FRAME)
