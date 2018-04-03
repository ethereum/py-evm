from cytoolz import (
    pipe,
)

from eth_utils import (
    event_signature_to_log_topic,
    to_dict,
    to_tuple,
    encode_hex,
    decode_hex,
    big_endian_to_int,
)

from evm.rlp.headers import (
    CollationHeader,
)


class NextLogUnavailable(Exception):
    pass


class NoCandidateHead(Exception):
    pass


# For handling logs filtering
# Event:
#   CollationAdded(indexed uint256 shard, bytes collationHeader, bool isNewHead, uint256 score)
COLLATION_ADDED_TOPIC = event_signature_to_log_topic(
    "CollationAdded(int128,int128,bytes32,bytes32,bytes32,address,bytes32,bytes32,int128,bool,int128)"  # noqa: E501
)


@to_dict
def parse_collation_added_log(log):
    # `shard_id` is the first indexed entry,hence the second entry in topics
    shard_id_bytes32 = log['topics'][1]
    data_bytes = decode_hex(log['data'])
    header_bytes = shard_id_bytes32 + data_bytes[:-64]
    is_new_head = bool(big_endian_to_int(data_bytes[-64:-32]))
    score = big_endian_to_int(data_bytes[-32:])
    collation_header = CollationHeader.from_bytes(header_bytes)
    yield 'header', collation_header
    yield 'is_new_head', is_new_head
    yield 'score', score


class ShardTracker:
    """Track logs `CollationAdded` in mainchain
    """

    current_score = None
    new_logs = None
    unchecked_logs = None

    def __init__(self, shard_id, log_handler, vmc_handler_address):
        # TODO: currently set one log_handler for each shard. Should see if there is a better way
        #       to make one log_handler shared over all shards.
        self.shard_id = shard_id
        self.log_handler = log_handler
        self.vmc_handler_address = vmc_handler_address
        self.current_score = None
        self.new_logs = []
        self.unchecked_logs = []

    @to_tuple
    def _get_new_logs(self):
        shard_id_topic_hex = encode_hex(self.shard_id.to_bytes(32, byteorder='big'))
        new_logs = self.log_handler.get_new_logs(
            address=self.vmc_handler_address,
            topics=[
                encode_hex(COLLATION_ADDED_TOPIC),
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
        current_score = self.current_score

        for idx, log_entry in unchecked_logs:
            if log_entry['score'] == current_score:
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
