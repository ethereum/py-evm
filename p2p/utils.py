import asyncio
import os
from typing import List

import rlp

from evm.utils.numeric import big_endian_to_int

from p2p.service import BaseService


def sxor(s1: bytes, s2: bytes) -> bytes:
    if len(s1) != len(s2):
        raise ValueError("Cannot sxor strings of different length")
    return bytes(x ^ y for x, y in zip(s1, s2))


def roundup_16(x):
    """Rounds up the given value to the next multiple of 16."""
    remainder = x % 16
    if remainder != 0:
        x += 16 - remainder
    return x


def gen_request_id():
    return big_endian_to_int(os.urandom(8))


def get_devp2p_cmd_id(msg: bytes) -> int:
    """Return the cmd_id for the given devp2p msg.

    The cmd_id, also known as the payload type, is always the first entry of the RLP, interpreted
    as an integer.
    """
    return rlp.decode(msg[:1], sedes=rlp.sedes.big_endian_int)


class RunningServices:
    def __init__(self, services: List[BaseService]) -> None:
        self.services = services

    async def __aenter__(self):
        for service in self.services:
            asyncio.ensure_future(service.run())

    async def __aexit__(self, exc_type, exc, tb):
        service_cancellations = [service.cancel() for service in self.services]
        await asyncio.gather(*service_cancellations, return_exceptions=True)
