from abc import ABC, abstractmethod
from typing import Tuple

from eth.rlp.headers import BlockHeader

from p2p.protocol import (
    Command,
    _DecodedMsgType,
)


class BaseBlockHeaders(ABC, Command):

    @abstractmethod
    def extract_headers(self, msg: _DecodedMsgType) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("Must be implemented by subclasses")
