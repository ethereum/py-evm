import copy

from evm.rlp.headers import (
    CollationHeader,
)

from evm.utils.hexadecimal import (
    encode_hex,
    decode_hex,
)
from evm.utils.numeric import (
    big_endian_to_int,
)


# For handling logs filtering
COLLATION_ADDED_EVENT_NAME = "CollationAdded"


def parse_collation_added_log(log):
    # here assume `shard_id` is the first indexed , which is the second element in topics
    shard_id_bytes32 = log['topics'][1]
    data_hex = log['data']
    data_bytes = decode_hex(data_hex)
    height = big_endian_to_int(data_bytes[-32:])
    is_new_head = bool(big_endian_to_int(data_bytes[-64:-32]))
    header_bytes = shard_id_bytes32 + data_bytes[:-64]
    collation_header = CollationHeader.from_bytes(header_bytes)
    return {
        'header': collation_header,
        'is_new_head': is_new_head,
        'height': height,
    }


def candidate_heads(headers_by_height, min_index, max_index):
    for height in reversed(range(min_index, max_index + 1)):
        for header in headers_by_height[height]:
            yield header


class ShardTracker:
    '''Track logs `CollationAdded` in mainchain
    '''

    shard_id = None
    log_handler = None
    smc_address = None
    collation_added_topic = None

    headers_by_height = None

    def __init__(self, shard_id, log_handler, smc_address, collation_added_topic):
        # TODO: currently set one log_handler for each shard. Should see if there is a better way
        #       to make one log_handler shared over all shards.
        self.shard_id = shard_id
        self.log_handler = log_handler
        self.smc_address = smc_address
        self.collation_added_topic = collation_added_topic

        # for the alternative `fetch_candidate_head`
        # TODO: might need to be a sliding window, discarding the headers which are no longer
        #       needed.
        #       However, still need to figure out the window size. Since we need to make sure that
        #       collation headers of non-best-candidate chains in the depth <= `WINDBACK_LENGTH`
        #       should still be reachable.
        self.headers_by_height = []

    def new_logs(self):
        shard_id_topic_hex = encode_hex(self.shard_id.to_bytes(32, byteorder='big'))
        logs = self.log_handler.get_new_logs(
            address=self.smc_address,
            topics=[
                encode_hex(self.collation_added_topic),
                shard_id_topic_hex,
            ],
        )
        for log in logs:
            yield parse_collation_added_log(log)

    def add_log(self, log_entry):
        collation_height = log_entry['height']
        while len(self.headers_by_height) <= collation_height:
            self.headers_by_height.append([])
        self.headers_by_height[collation_height].append(log_entry['header'])

    def fetch_candidate_heads_generator(self):
        for log_entry in self.new_logs():
            # TODO: we can use another coroutine to sync the logs concurrently, instead of doing
            #       that in this function
            self.add_log(log_entry)
        # TODO: deepcopy seems to be costly
        headers_by_height = copy.deepcopy(self.headers_by_height)
        return candidate_heads(headers_by_height, 0, len(headers_by_height) - 1)
