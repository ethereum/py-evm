from abc import abstractmethod
from typing import Tuple

from eth.rlp.headers import BlockHeader

from p2p.protocol import Command
from p2p.typing import PayloadType


class BaseBlockHeaders(Command):

    @abstractmethod
    def extract_headers(self, msg: PayloadType) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("Must be implemented by subclasses")
