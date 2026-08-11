"""Recordings are complete, mutually independent, and standard WAVs."""
import asyncio
import io
import wave

from mixer import MixSession
from mixer.constants import BYTES_PER_FRAME
from mixer.recorder import Recorder


def test_fifty_appended_frames_are_exactly_fifty_frames_of_audio():
    """Recording is byte-exact accumulation: fifty appended frames are fifty
    frames of audio, nothing dropped, nothing padded.
    """
    recorder = Recorder("a")
    for _ in range(50):
        recorder.append(bytes(BYTES_PER_FRAME))
    assert len(recorder.audio) == 50 * BYTES_PER_FRAME


def test_recorders_started_at_different_times_have_different_lengths():
    """Each recorder captures from its own start moment: one started earlier
    against the same live clock ends up strictly longer.
    """
    results = {}

    async def main():
        session = MixSession()
        await session.start()
        session.start_recording("early")
        await asyncio.sleep(0.2)
        session.start_recording("late")
        await asyncio.sleep(0.2)
        results["early"] = session.stop_recording("early")
        results["late"] = session.stop_recording("late")
        await session.close()

    asyncio.run(main())
    assert len(results["early"].audio) > len(results["late"].audio) > 0


def test_stopping_one_recorder_does_not_affect_the_other():
    """Stopping freezes only that recorder; the other keeps growing. Pins the
    independence of concurrent recordings.
    """
    results = {}

    async def main():
        session = MixSession()
        await session.start()
        session.start_recording("a")
        session.start_recording("b")
        await asyncio.sleep(0.1)
        results["a"] = session.stop_recording("a")
        len_a_at_stop = len(results["a"].audio)
        await asyncio.sleep(0.1)
        results["b"] = session.stop_recording("b")
        results["a_grew_after_stop"] = len(results["a"].audio) != len_a_at_stop
        await session.close()

    asyncio.run(main())
    assert not results["a_grew_after_stop"]  # stopped means stopped
    assert len(results["b"].audio) > len(results["a"].audio)  # b kept going


def test_stop_then_start_produces_two_independent_recorders():
    """Stop-then-start is a fresh recording, never a resume: two distinct
    objects, and the first stays exactly as it was when stopped.
    """
    results = {}

    async def main():
        session = MixSession()
        await session.start()
        session.start_recording("a")
        await asyncio.sleep(0.1)
        first = session.stop_recording("a")
        first_len = len(first.audio)
        session.start_recording("a")
        await asyncio.sleep(0.1)
        second = session.stop_recording("a")
        results.update(first=first, second=second, first_len=first_len)
        await session.close()

    asyncio.run(main())
    assert results["first"] is not results["second"]
    assert len(results["first"].audio) == results["first_len"]  # untouched
    assert len(results["second"].audio) > 0


def test_to_wav_is_parseable_at_16k_mono_16bit():
    """The stdlib wave module must accept the output and report our exact
    format, with a frame count matching the appended audio -- the recording
    is a standard file, not just our own bytes.
    """
    recorder = Recorder("a")
    for _ in range(25):
        recorder.append(bytes(BYTES_PER_FRAME))
    with wave.open(io.BytesIO(recorder.to_wav()), "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 25 * BYTES_PER_FRAME // 2
