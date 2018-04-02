import copy

from cytoolz import (
    pipe,
)

from eth_utils import (
    event_signature_to_log_topic,
    to_tuple,
)

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


class NextLogUnavailable(Exception):
    pass


class NoCandidateHead(Exception):
    pass


def parse_collation_added_log(log):
    # here assume `shard_id` is the first indexed , which is the second element in topics
    shard_id_bytes32 = log['topics'][1]
    data_hex = log['data']
    data_bytes = decode_hex(data_hex)
    score = big_endian_to_int(data_bytes[-32:])
    is_new_head = bool(big_endian_to_int(data_bytes[-64:-32]))
    header_bytes = shard_id_bytes32 + data_bytes[:-64]
    collation_header = CollationHeader.from_bytes(header_bytes)
    return {
        'header': collation_header,
        'is_new_head': is_new_head,
        'score': score,
    }


class ShardTracker:
    '''Track logs `CollationAdded` in mainchain
    '''
    # For handling logs filtering
    # Event:
    #   CollationAdded(indexed uint256 shard, bytes collationHeader, bool isNewHead, uint256 score)
    COLLATION_ADDED_TOPIC = event_signature_to_log_topic(
        "CollationAdded(int128,int128,bytes32,bytes32,bytes32,address,bytes32,bytes32,int128,bool,int128)"  # noqa: E501
    )

    current_score = None
    new_logs = None
    unchecked_logs = None
    headers_by_height = None

    def __init__(self, shard_id, log_handler, vmc_address):
        # TODO: currently set one log_handler for each shard. Should see if there is a better way
        #       to make one log_handler shared over all shards.
        self.shard_id = shard_id
        self.log_handler = log_handler
        self.vmc_address = vmc_address
        self.current_score = None
        self.new_logs = []
        self.unchecked_logs = []

        # for the alternative `fetch_candidate_head`
        # TODO: might need to be a sliding window, discarding the headers which are no longer
        #       needed.
        #       However, still need to figure out the window size. Since we need to make sure that
        #       collation headers of non-best-candidate chains in the depth <= `WINDBACK_LENGTH`
        #       should still be reachable.
        self.headers_by_height = []

    @to_tuple
    def _get_new_logs(self):
        shard_id_topic_hex = encode_hex(self.shard_id.to_bytes(32, byteorder='big'))
        new_logs = self.log_handler.get_new_logs(
            address=self.vmc_address,
            topics=[
                encode_hex(self.COLLATION_ADDED_TOPIC),
                shard_id_topic_hex,
            ],
        )
        for log in new_logs:
            yield parse_collation_added_log(log)

    def get_next_log(self):
        new_logs = self._get_new_logs()
        self.new_logs.extend(new_logs)
        if len(self.new_logs) == 0:
            raise NextLogUnavailable("No more next logs")
        return self.new_logs.pop()

    # TODO: this method may return wrong result when new logs arrive before the logs inside
    #       `self.new_logs` are consumed entirely. This issue can be resolved by saving the
    #       status of `new_logs`, `unchecked_logs`, and `current_score`, when it start to run
    #       `GUESS_HEAD`. If there is a new block arriving, just restore them to the saved status,
    #       append new logs to `new_logs`, and re-run `GUESS_HEAD`
    def fetch_candidate_head(self):
        # Try to return a log that has the score that we are checking for,
        # checking in order of oldest to most recent.
        unchecked_logs = pipe(
            self.unchecked_logs,
            enumerate,
            tuple,
            reversed,
            tuple,
        )
        for idx, log_entry in unchecked_logs:
            if log_entry['score'] == self.current_score:
                return self.unchecked_logs.pop(idx)
        # If no further recorded but unchecked logs exist, go to the next
        # is_new_head = true log
        while True:
            try:
                log_entry = self.get_next_log()
            # TODO: currently just raise when there is no log anymore
            except NextLogUnavailable:
                # TODO: should returns the genesis collation instead or just leave it?
                raise NoCandidateHead("No candidate head available")
            if log_entry['is_new_head']:
                break
            self.unchecked_logs.append(log_entry)
        self.current_score = log_entry['score']
        return log_entry

    def clean_logs(self):
        self.new_logs = []
        self.unchecked_logs = []

    def add_log(self, log_entry):
        collation_height = log_entry['score']
        while len(self.headers_by_height) <= collation_height:
            self.headers_by_height.append([])
        self.headers_by_height[collation_height].append(log_entry['header'])

    def fetch_candidate_heads_generator(self, windback_length):
        new_logs = self._get_new_logs()
        for log_entry in new_logs:
            # TODO: we can use another coroutine to sync the logs concurrently, instead of doing
            #       that in this function
            self.add_log(log_entry)
        # TODO: deepcopy seems to be costly
        headers_by_height = copy.deepcopy(self.headers_by_height)
        max_height = len(headers_by_height) - 1
        windback_index = max(0, max_height + 1 - windback_length)
        for height in reversed(range(windback_index, max_height + 1)):
            for header in headers_by_height[height]:
                yield header
