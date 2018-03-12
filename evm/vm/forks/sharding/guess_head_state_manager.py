from collections import (
    defaultdict,
)

import logging

from evm.vm.forks.sharding.vmc_handler import (
    NoCandidateHead,
)


GENESIS_COLLATION_HASH = b'\x00' * 32
NUM_RESERVED_BLOCKS = 5


def fetch_and_verify_collation(collation_hash):
    """Fetch the collation body and verify the collation

    :return: returns the collation's validity
    """
    # TODO: currently do nothing, should be implemented or imported when `fetch_collation` and
    #       `verify_collation` are implemented
    return True


def threaded_execute(function, *args, **kwargs):
    # TODO: fake thread, should be replaced by Threading or async
    function(*args, **kwargs)


def create_collation(parent_hash, data):
    # return collation with data with head = candidate_head
    # ablalalala
    print("!@# create_collation: parent_hash={}, data={}".format(
        parent_hash,
        data,
    ))
    return True


class GuessHeadStateManager:

    logger = logging.getLogger("evm.chain.sharding.GuessHeadStateManager")

    collation_validity_cache = None
    head_validity = None
    head_collation_hash = None
    last_period_fetching_candidate_head = None
    is_verifying_collations = None

    def __init__(self, vmc, shard_id, shard_tracker, my_address):
        # a well-setup vmc handler with a shard_tracker in shard `shard_id`
        self.vmc = vmc
        self.shard_id = shard_id
        self.shard_tracker = shard_tracker
        self.my_address = my_address

        # map[collation] -> validity
        self.collation_validity_cache = {}
        # map[chain_head] -> validity
        # this should be able to be updated by the collations' validity
        # TODO: need to check if it is thread-safe
        # TODO: no need to use dict, just a class member with threading.lock()
        #       should be okay?
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
        for future_periods in range(self.vmc.config['LOOKAHEAD_PERIODS']):
            lookahead_period = self.get_current_period() + future_periods
            result |= self.is_collator_in_period(lookahead_period)
        return result

    def is_collator_in_current_period(self):
        current_period = self.get_current_period()
        return self.is_collator_in_period(current_period)

    def is_late_collator_period(self):
        current_period = self.get_current_period()
        current_block_num = self.vmc.web3.eth.blockNumber
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
            head_collation_dict = self.shard_tracker.fetch_candidate_head()
            head_collation_hash = head_collation_dict['header'].hash
        except NoCandidateHead:
            self.logger.debug("No candidate head available, `guess_head` stops")
        self.last_period_fetching_candidate_head = self.get_current_period()
        return head_collation_hash

    def try_change_head(self):
        # check for head changing
        current_period = self.get_current_period()
        # if head and current are None in the same time, it means it is just started up
        # should try to get the head for it
        if ((self.head_collation_hash is None and self.current_collation_hash is None) or
                (current_period > self.last_period_fetching_candidate_head) or
                (not self.head_validity[self.head_collation_hash])):
            if current_period > self.last_period_fetching_candidate_head:
                # TODO: should check if it is correct
                # flush old candidate heads first, since all those candidates are stale
                self.shard_tracker.clean_logs()
            # perform head changing
            self.head_collation_hash = self.fetch_candidate_head_hash()
            if self.head_collation_hash is not None:
                self.current_collation_hash = self.head_collation_hash

    def process_current_collation(self):
        # only process collations when the node is collating
        if (self.is_verifying_collations and
                (self.head_collation_hash is not None) and
                (self.current_collation_hash != GENESIS_COLLATION_HASH)):
            # process current collation
            threaded_execute(
                self.process_collation,
                self.head_collation_hash,
                self.current_collation_hash,
            )
            self.current_collation_hash = self.vmc.get_parent_hash(
                self.shard_id,
                self.current_collation_hash,
            )

    def try_create_collation(self):
        # Check if it is time to collate  #################################
        if (self.head_collation_hash is None or
                (not self.head_validity[self.head_collation_hash])):
            return None
        # TODO: currently it is not correct,
        #       still need to check if all of the thread has finished,
        #       and the validity of head_collation is True
        is_to_create_collation = (
            self.is_late_collator_period() or
            self.current_collation_hash == GENESIS_COLLATION_HASH
        )
        if is_to_create_collation:
            head_collation_hash = self.head_collation_hash
            create_collation(head_collation_hash, data="123")
            self.head_collation_hash = None
            return head_collation_hash
        return None

    def guess_head_daemon(self, stop_after_create_collation=False):
        # At any time, there should be only one `head_collation`
        # The timing where `head_collation_hash` change are:
        #    1. `head_collation` is invalid, change to the new head
        #    2. There are new logs, and `fetch_candidate_head` is called
        # When to stop processing collation?
        self.head_collation_hash = self.current_collation_hash = None
        self.is_verifying_collations = False
        while True:
            self.is_verifying_collations = (
                self.is_collator_in_lookahead_periods() or
                self.head_collation_hash is None
            )
            self.try_change_head()
            self.process_current_collation()
            parent_hash = self.try_create_collation()
            if stop_after_create_collation and parent_hash is not None:
                return parent_hash
            # time.sleep(0.5)
            # input()
