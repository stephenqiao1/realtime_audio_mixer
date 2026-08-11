import numpy as np

from mixer import MixSession
from mixer.constants import DTYPE, SAMPLES_PER_FRAME


def frame(value):
    return np.full(SAMPLES_PER_FRAME, value, dtype=DTYPE).tobytes()


def test_single_device_audio_passes_through_unchanged():
    session = MixSession()
    session.add_participant("a")
    assert session.push("a", frame(1234)) == frame(1234)


def test_two_devices_mix_to_their_sum():
    session = MixSession()
    session.add_participant("a")
    session.add_participant("b")
    session.push("a", frame(1000))
    mixed = session.push("b", frame(2000))
    assert mixed == frame(3000)


def test_removed_participant_stops_appearing_in_the_mix():
    session = MixSession()
    session.add_participant("a")
    session.add_participant("b")
    session.push("a", frame(1000))
    session.push("b", frame(2000))
    session.remove_participant("b")
    assert session.participants() == ["a"]
    assert session.push("a", frame(1000)) == frame(1000)
