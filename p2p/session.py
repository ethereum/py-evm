from typing import Any, Optional
import uuid

from p2p.abc import NodeAPI, SessionAPI


class Session(SessionAPI):
    def __init__(self, remote: NodeAPI, session_id: Optional[uuid.UUID] = None) -> None:
        if session_id is None:
            session_id = uuid.uuid4()
        self.id = session_id
        self.remote = remote

    def __str__(self) -> str:
        return f"<Session {self.remote} {self.id}>"

    def __repr__(self) -> str:
        return f"Session({self.remote!r} {self.id!r})"

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        if not type(self) is type(other):
            return False
        return self.id == other.id
