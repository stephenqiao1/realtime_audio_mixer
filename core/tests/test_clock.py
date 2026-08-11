import asyncio

import numpy as np

from mixer import MixSession
from mixer.constants import DTYPE, SAMPLES_PER_FRAME


def frame(value):
    return np.full(SAMPLES_PER_FRAME, value, dtype=DTYPE).tobytes()


def first_sample(mixed):
    return int(np.frombuffer(mixed, dtype=DTYPE)[0])


def collect_from(queue, into):
    async def drainer():
        while True:
            into.append(await queue.get())
    return asyncio.create_task(drainer())


def test_clock_emits_fifty_frames_per_second():
    outputs = []

    async def main():
        session = MixSession()
        drainer = collect_from(session.subscribe(), outputs)
        await session.start()
        await asyncio.sleep(1.0)
        await session.close()
        drainer.cancel()

    asyncio.run(main())
    assert 48 <= len(outputs) <= 52


def test_silent_device_does_not_block_the_other():
    outputs = []

    async def main():
        session = MixSession()
        drainer = collect_from(session.subscribe(), outputs)
        session.add_participant("talker")
        session.add_participant("quiet")
        await session.start()
        for _ in range(5):
            session.push("talker", frame(1000))
            await asyncio.sleep(0.02)
        await session.close()
        drainer.cancel()

    asyncio.run(main())
    assert 1000 in {first_sample(o) for o in outputs}


def test_stopped_device_does_not_repeat_its_last_frame():
    outputs = []

    async def main():
        # depth 1: a single frame should prime immediately for this test
        session = MixSession(target_depth=1)
        drainer = collect_from(session.subscribe(), outputs)
        session.add_participant("a")
        await session.start()
        session.push("a", frame(5000))
        await asyncio.sleep(0.2)  # ~10 ticks, but only one push
        await session.close()
        drainer.cancel()

    asyncio.run(main())
    values = [first_sample(o) for o in outputs]
    assert values.count(5000) == 1  # heard exactly once, never repeated
    assert 0 in values  # the following ticks were silence
