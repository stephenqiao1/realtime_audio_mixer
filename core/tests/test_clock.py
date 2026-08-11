import asyncio

import numpy as np

from mixer import MixSession
from mixer.constants import DTYPE, SAMPLES_PER_FRAME


def frame(value):
    return np.full(SAMPLES_PER_FRAME, value, dtype=DTYPE).tobytes()


def first_sample(mixed):
    return int(np.frombuffer(mixed, dtype=DTYPE)[0])


def test_clock_emits_fifty_frames_per_second():
    outputs = []

    async def main():
        session = MixSession()

        async def collect(mixed):
            outputs.append(mixed)

        session.on_output(collect)
        await session.start()
        await asyncio.sleep(1.0)
        await session.close()

    asyncio.run(main())
    assert 48 <= len(outputs) <= 52


def test_silent_device_does_not_block_the_other():
    outputs = []

    async def main():
        session = MixSession()

        async def collect(mixed):
            outputs.append(mixed)

        session.on_output(collect)
        session.add_participant("talker")
        session.add_participant("quiet")
        await session.start()
        for _ in range(5):
            session.push("talker", frame(1000))
            await asyncio.sleep(0.02)
        await session.close()

    asyncio.run(main())
    assert 1000 in {first_sample(o) for o in outputs}


def test_stopped_device_does_not_repeat_its_last_frame():
    outputs = []

    async def main():
        session = MixSession()

        async def collect(mixed):
            outputs.append(mixed)

        session.on_output(collect)
        session.add_participant("a")
        await session.start()
        session.push("a", frame(5000))
        await asyncio.sleep(0.2)  # ~10 ticks, but only one push
        await session.close()

    asyncio.run(main())
    values = [first_sample(o) for o in outputs]
    assert values.count(5000) == 1  # heard exactly once, never repeated
    assert 0 in values  # the following ticks were silence
