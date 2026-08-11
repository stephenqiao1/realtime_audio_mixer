"""MixSession bookkeeping: store-only push, exact participant membership."""
import numpy as np

from mixer import MixSession
from mixer.constants import DTYPE, SAMPLES_PER_FRAME


def frame(value):
    return np.full(SAMPLES_PER_FRAME, value, dtype=DTYPE).tobytes()


def test_push_stores_the_frame_and_returns_nothing():
    """push() is store-only since the clock took over producing output;
    returning None is that contract, pinned so a regression to the old
    mix-on-push shape fails loudly.
    """
    session = MixSession()
    session.add_participant("a")
    assert session.push("a", frame(1234)) is None
    assert session.participants() == ["a"]


def test_removed_participant_is_forgotten():
    """remove_participant drops the device's slot entirely -- participants()
    reflects membership, and a departed device leaves no trace.
    """
    session = MixSession()
    session.add_participant("a")
    session.add_participant("b")
    session.push("b", frame(2000))
    session.remove_participant("b")
    assert session.participants() == ["a"]
