from abc import abstractmethod
from typing import Tuple

from eth.rlp.headers import BlockHeader

from p2p.protocol import Command
from p2p.typing import Payload


class BaseBlockHeaders(Command):

    @abstractmethod
    def extract_headers(self, msg: Payload) -> Tuple[BlockHeader, ...]:
        ...
