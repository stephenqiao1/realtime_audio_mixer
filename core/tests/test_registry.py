"""Rooms: isolation, code hygiene, lifecycle, recordings outlive closure."""
import asyncio
import io
import wave

import numpy as np
import pytest

from mixer import AudioMixer, RoomNotFound
from mixer.constants import DTYPE, SAMPLES_PER_FRAME
from mixer.registry import CODE_ALPHABET


def frame(value):
    return np.full(SAMPLES_PER_FRAME, value, dtype=DTYPE).tobytes()


def test_two_rooms_mix_independently():
    """Audio pushed into room A must never appear in room B's output --
    rooms are fully isolated sessions. Also pins case-insensitive lookup
    returning the same room object.
    """
    results = {}

    async def main():
        mixer = AudioMixer()
        code_a = await mixer.create_room()
        code_b = await mixer.create_room()
        room_a = mixer.get_room(code_a)
        room_b = mixer.get_room(code_b)
        assert mixer.get_room(code_a.lower()) is room_a  # case-insensitive
        queue_a, queue_b = room_a.subscribe(), room_b.subscribe()
        got_a, got_b = [], []

        async def drain(queue, into):
            while True:
                into.append(await queue.get())

        drains = [asyncio.create_task(drain(queue_a, got_a)),
                  asyncio.create_task(drain(queue_b, got_b))]
        for _ in range(8):
            room_a.push("talker", frame(1000))
            await asyncio.sleep(0.02)
        await mixer.close_room(code_a)
        await mixer.close_room(code_b)
        for task in drains:
            task.cancel()
        results["a"] = {int(np.frombuffer(f, DTYPE)[0]) for f in got_a}
        results["b"] = {int(np.frombuffer(f, DTYPE)[0]) for f in got_b}

    asyncio.run(main())
    assert 1000 in results["a"]
    assert results["b"] <= {0}  # room A's audio never leaked into room B


def test_get_room_on_unknown_code_raises():
    """get_room never creates: an unknown code is an error surfaced at the
    boundary, not a silently materialized empty room.
    """
    mixer = AudioMixer()
    with pytest.raises(RoomNotFound):
        mixer.get_room("ZZZZ")


def test_codes_are_unique_and_unambiguous_across_many_creates():
    """200 creates: every code distinct, 4 characters, drawn only from the
    alphabet with the lookalikes (O/0, I/1) removed.
    """
    results = {}

    async def main():
        mixer = AudioMixer()
        results["codes"] = [await mixer.create_room() for _ in range(200)]
        for code in list(mixer.rooms):
            await mixer.close_room(code)

    asyncio.run(main())
    codes = results["codes"]
    assert len(set(codes)) == 200
    assert all(len(c) == 4 and set(c) <= set(CODE_ALPHABET) for c in codes)


def test_close_room_cancels_the_clock_task():
    """Closing a room actually cancels its clock task (no orphaned 50 Hz
    loops) and removes it from the registry.
    """
    results = {}

    async def main():
        mixer = AudioMixer()
        code = await mixer.create_room()
        task = mixer.get_room(code)._task
        await mixer.close_room(code)
        results["cancelled"] = task.cancelled()
        results["exists"] = mixer.room_exists(code)

    asyncio.run(main())
    assert results["cancelled"]
    assert not results["exists"]


def test_recording_survives_room_closure():
    """WAV bytes extracted at stop time hold no reference to the session, so
    a recording remains readable after its room is gone.
    """
    results = {}

    async def main():
        mixer = AudioMixer()
        code = await mixer.create_room()
        room = mixer.get_room(code)
        room.start_recording("a")
        await asyncio.sleep(0.1)
        recorder = room.stop_recording("a")
        results["wav"] = recorder.to_wav()  # extracted before closure
        await mixer.close_room(code)

    asyncio.run(main())
    with wave.open(io.BytesIO(results["wav"]), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        assert w.getnframes() > 0


def test_last_participant_leaving_closes_the_room():
    """leave_room turns off the lights: the room survives the first leaver
    and closes exactly when the last participant departs.
    """
    results = {}

    async def main():
        mixer = AudioMixer()
        code = await mixer.create_room()
        room = mixer.get_room(code)
        room.add_participant("x")
        room.add_participant("y")
        await mixer.leave_room(code, "x")
        results["open_after_first"] = mixer.room_exists(code)
        await mixer.leave_room(code, "y")
        results["open_after_last"] = mixer.room_exists(code)

    asyncio.run(main())
    assert results["open_after_first"]
    assert not results["open_after_last"]
