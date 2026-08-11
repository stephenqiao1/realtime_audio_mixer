import asyncio

import numpy as np

from mixer import MixSession
from mixer.constants import DTYPE, SAMPLES_PER_FRAME


def frame(value):
    return np.full(SAMPLES_PER_FRAME, value, dtype=DTYPE).tobytes()


def drain(queue):
    frames = []
    while True:
        try:
            frames.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            return frames


def test_two_subscribers_both_receive_every_frame():
    results = {}

    async def main():
        session = MixSession()
        session.add_participant("a")
        q1 = session.subscribe()
        q2 = session.subscribe()
        await session.start()
        session.push("a", frame(1000))
        await asyncio.sleep(0.1)  # ~5 ticks, far below the queue bound
        await session.close()
        results["q1"], results["q2"] = drain(q1), drain(q2)

    asyncio.run(main())
    assert len(results["q1"]) >= 4
    assert results["q1"] == results["q2"]


def test_stalled_subscriber_drops_frames_without_affecting_the_other():
    received = []
    results = {}

    async def main():
        session = MixSession()
        stalled = session.subscribe()
        healthy = session.subscribe()

        async def drain_healthy():
            while True:
                received.append(await healthy.get())

        drainer = asyncio.create_task(drain_healthy())
        await session.start()
        await asyncio.sleep(1.3)  # ~65 ticks, past the 50-frame bound
        await session.close()
        drainer.cancel()
        results["stalled_dropped"] = session.dropped_frames(stalled)
        results["healthy_dropped"] = session.dropped_frames(healthy)
        results["stalled_backlog"] = stalled.qsize()

    asyncio.run(main())
    assert results["stalled_dropped"] > 0
    assert results["stalled_backlog"] == 50  # bounded, not growing forever
    assert results["healthy_dropped"] == 0
    assert len(received) >= 60  # the healthy subscriber missed nothing


def test_unsubscribe_stops_delivery_and_the_loop_survives():
    results = {}

    async def main():
        session = MixSession()
        q1 = session.subscribe()
        q2 = session.subscribe()
        await session.start()
        await asyncio.sleep(0.1)
        session.unsubscribe(q1)
        frozen = q1.qsize()
        await asyncio.sleep(0.1)
        results["q1_before"], results["q1_after"] = frozen, q1.qsize()
        results["q2_kept_growing"] = q2.qsize() > frozen
        await session.close()

    asyncio.run(main())
    assert results["q1_after"] == results["q1_before"]  # no delivery after unsubscribe
    assert results["q2_kept_growing"]  # the loop went on ticking for others
