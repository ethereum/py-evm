from collections import (
    OrderedDict,
    defaultdict,
)

import logging

from evm.vm.forks.sharding.vmc_handler import (
    NoCandidateHead,
    fetch_and_verify_collation,
)


GENESIS_COLLATION_HASH = b'\x00' * 32
NUM_RESERVED_BLOCKS = 5


def threaded_execute(function, *args, **kwargs):
    # TODO: fake thread, should be replaced by Threading or async
    function(*args, **kwargs)


def create_collation(data):
    # return collation with data with head = candidate_head
    # ablalalala
    print("!@# collation={} created".format(data))
    return True


class GuessHeadStateManager:

    logger = logging.getLogger("evm.chain.sharding.GuessHeadStateManager")

    collation_validity_cache = None
    head_validity = None
    last_period_fetching_candidate_head = None
    is_verifying_collations = None

    def __init__(self, vmc, shard_id, my_address):
        # a well-setup vmc handler with a shard_tracker in shard `shard_id`
        self.vmc = vmc
        self.shard_id = shard_id
        self.my_address = my_address

        # map[collation] -> validity
        self.collation_validity_cache = {}
        # map[chain_head] -> validity
        # this should be able to be updated by the collations' validity
        # TODO: need to check if it is thread-safe
        self.head_validity = defaultdict(lambda: True)
        # list of chain head, to indicate priority
        # order: older -------> newer
        self.last_period_fetching_candidate_head = 0
        # map[collation] -> thread
        self.collation_thread = []
        self.is_verifying_collations = False

    def get_current_period(self):
        return self.vmc.web3.eth.blockNumber // self.vmc.config['PERIOD_LENGTH']

    def is_collator_in_period(self, period):
        collator_address = self.vmc.get_eligible_proposer(
            self.shard_id,
            period,
        )
        return collator_address == self.my_address

    def is_collator_in_lookahead_periods(self):
        """
        See if we are going to be collator in the future periods
        """
        result = False
        for future_periods in self.vmc.config['LOOKAHEAD_PERIODS']:
            lookahead_period = self.get_current_period() + future_periods
            result |= self.is_collator_in_period(lookahead_period)
        return result

    def is_collator_in_current_period(self):
        current_period = self.get_current_period()
        return self.is_collator_in_period(current_period)

    def is_time_to_collate(self):
        current_period = self.get_current_period()
        current_block_num  = self.vmc.web3.eth.blockNumber
        last_block_num_in_current_period = current_period * self.vmc.config['PERIOD_LENGTH']
        return (
            self.is_collator_in_period(current_period) and
            (current_block_num + NUM_RESERVED_BLOCKS >= last_block_num_in_current_period)
        )

    def verify_collation(self, collation_hash):
        # TODO: thread-safe, not sure if GIL is countable
        if collation_hash not in self.collation_validity_cache:
            self.collation_validity_cache[collation_hash] = fetch_and_verify_collation(
                collation_hash,
            )
        return self.collation_validity_cache[collation_hash]

    def process_collation(self, head_collation_hash, checking_collation_hash):
        """
        Verfiy collation and return the result.
        If the verification fails(`self.verify_collation` returns False),
        indicate the current chain which we are verifying is invalid,
        should jump to another candidate chain
        """
        result = self.verify_collation(checking_collation_hash)
        if not result:
            # TODO: thread-safe right?
            self.head_validity[head_collation_hash] = False

    def fetch_candidate_head_hash(self):
        head_collation_hash = None
        try:
            head_collation_dict = self.vmc.fetch_candidate_head(self.shard_id)
            head_collation_hash = head_collation_dict['header'].hash
        except NoCandidateHead:
            self.logger.debug("No candidate head available, `guess_head` stops")
        self.last_period_fetching_candidate_head = self.get_current_period()
        return head_collation_hash

    def main(self):
        # At any time, there should be only one `head_collation`
        # The timing where `head_collation_hash` change are:
        #    1. `head_collation` is invalid, change to the new head
        #    2. There are new logs, and `fetch_candidate_head` is called
        # When to stop processing collation?
        head_collation_hash = None
        while True:
            # Actual `tick_guess_head` body  ##################################
            if self.is_collator_in_lookahead_periods():
                self.is_verifying_collations = True

            # Check for head changing
            current_period = self.get_current_period()
            if ((current_period > self.last_period_fetching_candidate_head) or
                    (head_collation_hash is None) or
                    (not self.head_validity[head_collation_hash])):
                if current_period > self.last_period_fetching_candidate_head:
                    # Should flush old candidate heads first, since all those candidates are stale
                    shard_tracker = self.vmc.get_shard_tracker(self.shard_id)
                    shard_tracker.clean_logs()
                head_collation_hash = self.fetch_candidate_head_hash()
                current_collation_hash = head_collation_hash

            # tick guess head: only process collations when the node is collating
            if self.is_verifying_collations and (head_collation_hash is not None):
                # process current collation
                threaded_execute(
                    self.process_collation,
                    head_collation_hash,
                    current_collation_hash,
                )
                current_collation_hash = self.vmc.get_parent_hash(
                    self.shard_id,
                    current_collation_hash,
                )

            # Check if it is time to collate  #################################
            if self.is_time_to_collate():
                # create collation
                create_collation("123")
            # Stop collating anyway, if we are still in periods where we should collate,
            # `self.is_verifying_collations` will be set to True again
            self.is_verifying_collations = False

            # TODO: when to stop ?
            # TODO: what to do when current_collation_hash == genesis?
