from eth_hash.auto import keccak

import rlp

from typing import (
    Iterable,
    Tuple,
)

from eth_typing import (
    Hash32,
)

from eth.rlp.logs import Log


def hash_log_entries(log_entries: Iterable[Tuple[bytes, Tuple[int, ...], bytes]]) -> Hash32:
    """
    Helper function for computing the RLP hash of the logs from transaction
    execution.
    """
    logs = [Log(*entry) for entry in log_entries]
    encoded_logs = rlp.encode(logs)
    logs_hash = keccak(encoded_logs)
    return logs_hash
