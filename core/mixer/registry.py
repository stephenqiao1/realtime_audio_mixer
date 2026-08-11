"""Room registry: many independent MixSessions addressed by short codes."""
import secrets

from mixer.session import MixSession

# Uppercase letters and digits minus the lookalikes O/0 and I/1.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4


class RoomNotFound(Exception):
    pass


class AudioMixer:
    """Creates, looks up and closes rooms. Codes are stored uppercase and
    looked up case-insensitively."""

    def __init__(self) -> None:
        self.rooms: dict[str, MixSession] = {}

    async def create_room(self) -> str:
        while True:
            code = "".join(
                secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self.rooms:
                break
        session = MixSession()
        self.rooms[code] = session
        await session.start()
        return code

    def get_room(self, code: str) -> MixSession:
        try:
            return self.rooms[code.upper()]
        except KeyError:
            raise RoomNotFound(code) from None

    def room_exists(self, code: str) -> bool:
        return code.upper() in self.rooms

    async def close_room(self, code: str) -> None:
        # Idempotent: the last-leaver path and an explicit close may race.
        session = self.rooms.pop(code.upper(), None)
        if session is not None:
            await session.close()

    async def leave_room(self, code: str, device_id: str) -> None:
        # The registry, not the transport, owns room lifecycle: the last
        # participant out turns off the lights.
        session = self.get_room(code)
        session.remove_participant(device_id)
        if not session.participants():
            await self.close_room(code)
