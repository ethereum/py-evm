import logging
from typing import (  # noqa: F401
    Dict
)

from cytoolz import (
    pipe,
)

from web3.contract import (
    Contract,
)

from eth_utils import (
    event_signature_to_log_topic,
    is_canonical_address,
    to_checksum_address,
    to_dict,
    to_tuple,
)

from evm.constants import (
    ZERO_HASH32,
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

from evm.vm.forks.sharding.config import (
    get_sharding_config,
)


class NextLogUnavailable(Exception):
    pass


class NoCandidateHead(Exception):
    pass


class UnknownShard(Exception):
    pass


def is_time_to_make_collation():
    # TODO: currently just for testing.
    #       should check if it is time to stop verification, and to make collations
    return False


def fetch_and_verify_collation(collation_hash):
    """Fetch the collation body and verify the collation

    :return: returns the collation's validity
    """
    # TODO: currently do nothing, should be implemented or imported when `fetch_collation` and
    #       `verify_collation` are implemented
    return True


@to_dict
def parse_collation_added_log(log):
    # here assume `shard_id` is the first indexed , which is the second element in topics
    shard_id_bytes32 = log['topics'][1]
    data_hex = log['data']
    data_bytes = decode_hex(data_hex)
    score = big_endian_to_int(data_bytes[-32:])
    is_new_head = bool(big_endian_to_int(data_bytes[-64:-32]))
    header_bytes = shard_id_bytes32 + data_bytes[:-64]
    collation_header = CollationHeader.from_bytes(header_bytes)
    yield 'header', collation_header
    yield 'is_new_head', is_new_head
    yield 'score', score


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

    def __init__(self, shard_id, log_handler, vmc_address):
        # TODO: currently set one log_handler for each shard. Should see if there is a better way
        #       to make one log_handler shared over all shards.
        self.shard_id = shard_id
        self.log_handler = log_handler
        self.vmc_address = vmc_address
        self.current_score = None
        self.new_logs = []
        self.unchecked_logs = []

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


class VMC(Contract):

    logger = logging.getLogger("evm.chain.sharding.VMC")

    def __init__(self, *args, default_privkey, **kwargs):
        self.default_privkey = default_privkey
        self.default_sender_address = default_privkey.public_key.to_canonical_address()
        self.config = get_sharding_config()
        self.shard_trackers = {}  # type: Dict[int, ShardTracker]

        self.collation_validity_cache = {}

        super().__init__(*args, **kwargs)

    def get_default_sender_address(self):
        return self.default_sender_address

    def set_shard_tracker(self, shard_id, shard_tracker):
        self.shard_trackers[shard_id] = shard_tracker

    def get_shard_tracker(self, shard_id):
        if shard_id not in self.shard_trackers:
            raise UnknownShard('Shard {} is not tracked'.format(shard_id))
        return self.shard_trackers[shard_id]

    # TODO: currently just calls `shard_tracker.get_next_log`
    def get_next_log(self, shard_id):
        shard_tracker = self.get_shard_tracker(shard_id)
        return shard_tracker.get_next_log()

    # TODO: currently just calls `shard_tracker.fetch_candidate_head`
    def fetch_candidate_head(self, shard_id):
        shard_tracker = self.get_shard_tracker(shard_id)
        return shard_tracker.fetch_candidate_head()

    def memoized_fetch_and_verify_collation(self, collation_hash):
        # Download a single collation and check if it is valid or invalid (memoized)
        if collation_hash not in self.collation_validity_cache:
            self.collation_validity_cache[collation_hash] = fetch_and_verify_collation(
                collation_hash,
            )
        return self.collation_validity_cache[collation_hash]

    def _verify_chain(self, shard_id, head_collation_hash):
        """Verify a chain and returns its validity.
        :return: returns the validity of the chain. if the time is out, returns True
        """
        current_collation_hash = head_collation_hash
        # if current_collation_hash == ZERO_HASH32, it means the whole chain of
        # the head `head_collation_hash` is valid.
        self.logger.debug(
            "Start verifying candidate chain with head {0}".format(head_collation_hash)
        )
        while not is_time_to_make_collation():
            if current_collation_hash == ZERO_HASH32:
                break
            if not self.memoized_fetch_and_verify_collation(current_collation_hash):
                return False
            current_collation_hash = self.get_parent_hash(shard_id, current_collation_hash)
        return True

    def guess_head(self, shard_id):
        """Pick the longest valid chain, check validity as far as possible, and if you find
           it's invalid then switch to the next-highest-scoring valid chain you know about.
           Should only stop when the validator runs out of time and it is time to create
           the collation

        :return: returns the hash of the guessed head collation
        """
        head_collation_hash = None
        while not is_time_to_make_collation():
            try:
                head_collation_dict = self.fetch_candidate_head(shard_id)
                head_collation_hash = head_collation_dict['header'].hash
            except NoCandidateHead:
                self.logger.debug("No candidate head available, `guess_head` stops")
                break
            # stop when we find a valid chain or run out of time
            if self._verify_chain(shard_id, head_collation_hash):
                break
        self.logger.debug("Guess {0} as head".format(head_collation_hash))
        return head_collation_hash

    @to_dict
    def mk_build_transaction_detail(self,
                                    nonce,
                                    gas,
                                    chain_id=None,
                                    value=None,
                                    gas_price=None,
                                    data=None):
        if not (isinstance(nonce, int) and nonce >= 0):
            raise ValueError('nonce should be provided as non-negative integer')
        if not (isinstance(gas, int) and gas > 0):
            raise ValueError('gas should be provided as positive integer')
        yield 'nonce', nonce
        yield 'gas', gas
        yield 'chainId', chain_id
        if value is not None:
            yield 'value', value
        if gas_price is not None:
            yield 'gasPrice', gas_price
        if data is not None:
            yield 'data', data

    def send_transaction(self,
                         func_name,
                         args,
                         nonce=None,
                         chain_id=None,
                         gas=None,
                         value=0,
                         gas_price=None,
                         data=None):
        if gas is None:
            gas = self.config['DEFAULT_GAS']
        if gas_price is None:
            gas_price = self.config['GAS_PRICE']
        privkey = self.default_privkey
        if nonce is None:
            nonce = self.web3.eth.getTransactionCount(privkey.public_key.to_checksum_address())
        build_transaction_detail = self.mk_build_transaction_detail(
            nonce=nonce,
            gas=gas,
            chain_id=chain_id,
            value=value,
            gas_price=gas_price,
            data=data,
        )
        func_instance = getattr(self.functions, func_name)
        unsigned_transaction = func_instance(*args).buildTransaction(
            transaction=build_transaction_detail,
        )
        signed_transaction_dict = self.web3.eth.account.signTransaction(
            unsigned_transaction,
            privkey.to_hex(),
        )
        tx_hash = self.web3.eth.sendRawTransaction(signed_transaction_dict['rawTransaction'])
        return tx_hash

    @to_dict
    def mk_contract_tx_detail(self,
                              sender_address,
                              gas,
                              value=None,
                              gas_price=None,
                              data=None):
        # Both 'from' and 'gas' are required in eth_tester
        if not is_canonical_address(sender_address):
            raise ValueError('sender_address should be provided in the canonical format')
        if not (isinstance(gas, int) and gas > 0):
            raise ValueError('gas should be provided as positive integer')
        yield 'from', to_checksum_address(sender_address)
        yield 'gas', gas
        if value is not None:
            yield 'value', value
        if gas_price is not None:
            yield 'gas_price', gas_price
        if data is not None:
            yield 'data', data

    # contract calls ##############################################

    def get_eligible_proposer(self, shard_id, period=None, gas=None):
        """Get the eligible proposer in the specified period
        """
        if gas is None:
            gas = self.config['DEFAULT_GAS']
        if period is None:
            period = self.web3.eth.blockNumber // self.config['PERIOD_LENGTH']
        tx_detail = self.mk_contract_tx_detail(sender_address=self.default_sender_address, gas=gas)
        address_in_hex = self.functions.get_eligible_proposer(shard_id, period).call(tx_detail)
        return decode_hex(address_in_hex)

    def get_parent_hash(self, shard_id, collation_hash, gas=None):
        if gas is None:
            gas = self.config['DEFAULT_GAS']
        tx_detail = self.mk_contract_tx_detail(sender_address=self.default_sender_address, gas=gas)
        return self.functions.get_collation_headers__parent_hash(
            shard_id,
            collation_hash,
        ).call(tx_detail)

    def deposit(self, gas=None, gas_price=None):
        """Do deposit to become a validator
        """
        tx_hash = self.send_transaction(
            'deposit',
            [],
            value=self.config['DEPOSIT_SIZE'],
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def withdraw(self, validator_index, gas=None, gas_price=None):
        """Withdraw the validator whose index is `validator_index`
        """
        tx_hash = self.send_transaction(
            'withdraw',
            [
                validator_index,
            ],
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def add_header(self,
                   collation_header,
                   gas=None,
                   gas_price=None):
        """Add the collation header with the given parameters
        """
        tx_hash = self.send_transaction(
            'add_header',
            [
                collation_header.shard_id,
                collation_header.expected_period_number,
                collation_header.period_start_prevhash,
                collation_header.parent_hash,
                collation_header.transaction_root,
                to_checksum_address(collation_header.coinbase),
                collation_header.state_root,
                collation_header.receipt_root,
                collation_header.number,
            ],
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def tx_to_shard(self,
                    to,
                    shard_id,
                    tx_startgas,
                    tx_gasprice,
                    data,
                    value,
                    gas=None,
                    gas_price=None):
        """Make a receipt with the given parameters
        """
        tx_hash = self.send_transaction(
            'tx_to_shard',
            [
                to_checksum_address(to),
                shard_id,
                tx_startgas,
                tx_gasprice,
                data,
            ],
            value=value,
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash
