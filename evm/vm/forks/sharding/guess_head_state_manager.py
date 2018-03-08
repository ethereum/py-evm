from evm.vm.forks.sharding.vmc_handler import (
    fetch_and_verify_collation,
)


GENESIS_COLLATION_HASH = b'\x00' * 32


class GuessHeadStateManager:

    collation_validity_cache = None
    candidate_head_hash = None
    checking_collation_hash = None

    def __init__(self, vmc, shard_id, my_address):
        # a well-setup vmc handler for shard_trackers in shard `shard_id`
        self.vmc = vmc
        self.shard_id = shard_id
        self.my_address = my_address

        self.collation_validity_cache = {}

    def verify_collation(self, collation_hash):
        if collation_hash not in self.collation_validity_cache:
            self.collation_validity_cache[collation_hash] = fetch_and_verify_collation(
                collation_hash,
            )
        return self.collation_validity_cache[collation_hash]

    def process_current_collation(self):
        """
        Verfiy collation and return the result.
        If the verification fails(`self.verify_collation` returns False),
        indicate the current chain which we are verifying is invalid,
        should jump to another candidate chain
        """
        result = self.verify_collation(self.checking_collation_hash)
        if result:
            self.checking_collation_hash = self.vmc.self.get_parent_hash(
                self.shard_id,
                self.checking_collation_hash,
            )
        # this collation is invalid, so don't check the candidate head anymore
        else:
            self.candidate_head_hash = None
        return result

    def tick_guess_head(self):
        # if there is no candidate head,
        # find one invalid, jump to the next chain
        if self.candidate_head_hash is None:
            candidate_head_hash = self.vmc.fetch_candidate_head(self.shard_id)
            # No candidate head now, should stop
            if candidate_head_hash == GENESIS_COLLATION_HASH:
                raise ValueError("No candidate head")
            self.candidate_head_hash = candidate_head_hash
            self.checking_collation_hash = candidate_head_hash
        # there is candidate head, process the current collation
        return self.process_current_collation()

    def create_collation(self, data):
        # return collation with data with head = candidate_head
        collation = True # ablalalala
        return collation

    def get_current_period(self):
        return self.vmc.web3.eth.blockNumber // self.vmc.config['PERIOD_LENGTH']

    def is_collator_in_period(self, period):
        collator_address = self.vmc.get_eligible_proposer(
            self.shard_id,
            period,
        )
        return collator_address == self.my_address

    def is_collator_in_lookahead_period(self):
        lookahead_period = self.get_current_period() + self.vmc.config['LOOKAHEAD_PERIODS']
        return self.is_collator_in_period(lookahead_period)

    def is_collator_in_current_period(self):
        current_period = self.get_current_period()
        return self.is_collator_in_period(current_period)

    def main(self):
        while True:
            if self.is_collator_in_lookahead_period():
                # run verify chain for current candidate_head
            if self.is_collator_in_current_period():
                # peek if there are new logs
                shard_tracker = self.vmc.get_shard_tracker[self.shard_id]
                new_logs = shard_tracker.peek_new_logs()
                # if there are new logs, should run `guess_head` again
                if len(new_logs) != 0:
                    # resetup candidate head hash
                    self.candidate_head_hash = None

                # setup candidate head hash
                self.candidate_head_hash = None

            # case3: need to stop guess_head and go create collations
            else:
                tx_data = []
                self.create_collation(tx_data)
                return
            self.tick_guess_head()
