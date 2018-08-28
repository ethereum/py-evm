from eth_hash.auto import keccak

import rlp

from eth.rlp.logs import Log


def hash_log_entries(log_entries):
    """
    Helper function for computing the RLP hash of the logs from transaction
    execution.
    """
    logs = [Log(*entry) for entry in log_entries]
    encoded_logs = rlp.encode(logs)
    logs_hash = keccak(encoded_logs)
    return logs_hash
