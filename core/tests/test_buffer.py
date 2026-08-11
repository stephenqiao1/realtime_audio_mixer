import asyncio

import numpy as np

from mixer import MixSession
from mixer.buffer import SILENCE, JitterBuffer
from mixer.constants import DTYPE, SAMPLES_PER_FRAME


def frame(value):
    return np.full(SAMPLES_PER_FRAME, value, dtype=DTYPE).tobytes()


def test_burst_then_empty_ticks_yield_all_frames_then_silence():
    buf = JitterBuffer()
    for value in range(1, 6):
        buf.push(frame(value))
    popped = [buf.pop() for _ in range(9)]
    assert popped[:5] == [frame(value) for value in range(1, 6)]
    assert popped[5:] == [SILENCE] * 4
    assert buf.underruns == 4


def test_overflow_drops_the_oldest_frame_not_the_newest():
    buf = JitterBuffer(max_depth=10)
    for value in range(12):
        buf.push(frame(value))
    assert buf.overruns == 2
    assert buf.pop() == frame(2)  # frames 0 and 1 were sacrificed
    for _ in range(8):
        buf.pop()
    assert buf.pop() == frame(11)  # the newest survived


def test_pop_on_empty_returns_silence_and_counts_the_underrun():
    buf = JitterBuffer()
    assert buf.pop() == SILENCE
    assert buf.underruns == 1


def test_split_pushes_reassemble_into_exactly_two_frames():
    outputs = []

    async def main():
        session = MixSession(target_depth=1)
        session.add_participant("a")
        data = frame(7) + frame(8)  # 1280 bytes
        session.push("a", data[:1000])
        session.push("a", data[1000:])  # remaining 280 bytes
        queue = session.subscribe()

        async def drainer():
            while True:
                outputs.append(await queue.get())

        task = asyncio.create_task(drainer())
        await session.start()
        await asyncio.sleep(0.1)
        await session.close()
        task.cancel()

    asyncio.run(main())
    audible = [o for o in outputs if o != SILENCE]
    assert audible == [frame(7), frame(8)]  # whole, ordered, uncorrupted


def test_late_joiner_does_not_disturb_the_other_device():
    outputs = []

    async def main():
        session = MixSession()  # default target_depth=3
        session.add_participant("a")
        for _ in range(3):
            session.push("a", frame(1000))  # primed before the clock starts
        queue = session.subscribe()

        async def drainer():
            while True:
                outputs.append(await queue.get())

        task = asyncio.create_task(drainer())
        await session.start()
        for tick in range(10):
            session.push("a", frame(1000))
            if tick == 5:
                session.add_participant("b")
                session.push("b", frame(9999))  # one frame: below the cushion
            await asyncio.sleep(0.02)
        await session.close()
        task.cancel()

    asyncio.run(main())
    values = {int(np.frombuffer(o, dtype=DTYPE)[0]) for o in outputs}
    assert 1000 in values       # the steady device kept playing
    assert values <= {0, 1000}  # never 9999, never a 10999 sum
