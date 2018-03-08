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

    def process_collation(self):
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
        return self.process_collation()

    def create_collation(self, data):
        # return collation with data with head = candidate_head
        collation = True # ablalalala
        return collation

    def main(self):
        while True:
            current_period = self.vmc.web3.eth.blockNumber // self.vmc.config['PERIOD_LENGTH']
            current_collator_address = self.vmc.get_eligible_proposer(
                self.shard_id,
                current_period,
            )
            lookahead_period = current_period + self.vmc.config['LOOKAHEAD_PERIODS']
            lookahead_collator_address = self.vmc.get_eligible_proposer(
                self.shard_id,
                lookahead_period,
            )
            # case1: try vmc.get_eligible_proposer(period+4)
            if lookahead_collator_address == self.my_address:
                # setup candidate head hash
                self.candidate_head_hash = None
            # case2: try vmc.get_eligible_proposer(period)
            elif current_collator_address == self.my_address:
                # peek if there are new logs
                shard_tracker = self.vmc.get_shard_tracker[self.shard_id]
                new_logs = shard_tracker.peek_new_logs()
                # if there are new logs, should run `guess_head` again
                if len(new_logs) != 0:
                    # resetup candidate head hash
                    self.candidate_head_hash = None
            # case3: need to stop guess_head and go create collations
            else:
                tx_data = []
                self.create_collation(tx_data)
                return
            self.tick_guess_head()
