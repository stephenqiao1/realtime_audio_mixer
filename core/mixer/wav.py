"""In-memory WAV encoding for 16 kHz mono 16-bit audio."""
import io
import wave

from mixer.constants import SAMPLE_RATE


def encode_wav(audio: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setframerate(SAMPLE_RATE)
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit samples
        w.writeframes(audio)
    return buf.getvalue()
