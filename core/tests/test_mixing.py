"""Pure mixing math: summing, clipping, silence identity, output length."""
import numpy as np

from mixer.constants import DTYPE, SAMPLE_RATE
from mixer.mixing import mix_streams


def sine_audio(amplitude, seconds=0.1, freq=440.0): # Generate a sine wave audio byte stream with the given amplitude, duration, and frequency.
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(DTYPE).tobytes()


def test_two_tones_sum_without_wraparound(): # Test that mixing two tones of moderate amplitude does not cause wraparound in the int16 range.
    """Two in-phase tones at amplitude 8000 must sum to ~16000: well inside
    int16, so the mix has to be the plain sample-wise sum. A signed overflow
    would betray itself as a large negative minimum.
    """
    tone = sine_audio(8000)
    mixed = np.frombuffer(mix_streams([tone, tone]), dtype=DTYPE)
    assert 15900 <= mixed.max() <= 16000
    assert mixed.min() >= -16000  # a wraparound would show up near -32768


def test_loud_tones_clamp_at_int16_range(): # Test that mixing two loud tones clamps the output to the int16 range.
    """Two tones at 30000 sum far past int16. The mix must saturate at the
    range edges (clip), never wrap around into noise.
    """
    tone = sine_audio(30000)
    mixed = np.frombuffer(mix_streams([tone, tone]), dtype=DTYPE)
    assert mixed.max() == 32767
    assert mixed.min() == -32768


def test_mixing_with_silence_is_identity(): # Test that mixing a tone with silence returns the original tone.
    """All-zero samples add nothing, so mixing with a silent stream must
    return the other stream byte-for-byte unchanged.
    """
    tone = sine_audio(8000)
    silence = b"\x00" * len(tone)
    assert mix_streams([tone, silence]) == tone


def test_output_matches_longest_stream(): # Test that mixing streams of different lengths produces an output that matches the longest stream, with shorter streams contributing silence after they are exhausted.
    """Streams of different lengths: the shorter one contributes silence once
    exhausted, and the output is exactly as long as the longest input. The
    480-sample stream (1.5 frames) also exercises internal frame padding.
    """
    long = sine_audio(8000, seconds=0.1)    # 1600 samples, frame-aligned
    short = sine_audio(8000, seconds=0.03)  # 480 samples, 1.5 frames
    mixed = mix_streams([long, short])
    assert len(mixed) == len(long)
    assert mixed[len(short):] == long[len(short):]  # tail is long alone
