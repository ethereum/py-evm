# Events
CollationAdded: __log__({
    shard_id: indexed(int128),
    expected_period_number: int128,
    period_start_prevhash: bytes32,
    parent_hash: bytes32,
    transaction_root: bytes32,
    collation_coinbase: address,
    state_root: bytes32,
    receipt_root: bytes32,
    collation_number: int128,
    is_new_head: bool,
    score: int128,
})
# TODO: determine the signature of the log `Deposit` and `Withdraw`
Deposit: __log__({validator_index: int128, validator_addr: address, deposit: wei_value})
Withdraw: __log__({validator_index: int128, validator_addr: address, deposit: wei_value})


# Information about validators
validators: public({
    # Amount of wei the validator holds
    deposit: wei_value,
    # Address of the validator
    addr: address,
}[int128])

# Number of validators
num_validators: public(int128)

# Collation headers: (parent_hash || score)
# parent_hash: 26 bytes
# score: 6 bytes
collation_headers: public(bytes32[bytes32][int128])

# Receipt data
receipts: public({
    shard_id: int128,
    tx_startgas: int128,
    tx_gasprice: int128,
    value: wei_value,
    sender: address,
    to: address,
    data: bytes <= 4096,
}[int128])

# Current head of each shard
shard_head: public(bytes32[int128])

# Number of receipts
num_receipts: int128

# Indexs of empty slots caused by the function `withdraw`
empty_slots_stack: int128[int128]

# The top index of the stack in empty_slots_stack
empty_slots_stack_top: int128

# Has the validator deposited before?
is_validator_deposited: public(bool[address])

# Log the latest period number of the shard
period_head: public(int128[int128])


# Configuration Parameter

# The exact deposit size which you have to deposit to become a validator
deposit_size: wei_value

# Number of blocks in one period
period_length: int128

# Number of shards
shard_count: int128

# Number of periods ahead of current period, which the contract
# is able to return the collator of that period
lookahead_periods: int128


@public
def __init__():
    self.num_validators = 0
    self.empty_slots_stack_top = 0
    # 10 ** 20 wei = 100 ETH
    self.deposit_size = 100000000000000000000
    self.period_length = 5
    self.shard_count = 100
    self.lookahead_periods = 4


# Checks if empty_slots_stack_top is empty
@private
def is_stack_empty() -> bool:
    return (self.empty_slots_stack_top == 0)


# Pushes one int128 to empty_slots_stack
@private
def stack_push(index: int128):
    self.empty_slots_stack[self.empty_slots_stack_top] = index
    self.empty_slots_stack_top += 1


# Pops one int128 out of empty_slots_stack
@private
def stack_pop() -> int128:
    if self.is_stack_empty():
        return -1
    self.empty_slots_stack_top -= 1
    return self.empty_slots_stack[self.empty_slots_stack_top]


# Returns the current maximum index for validators mapping
@private
@constant
def get_validators_max_index() -> int128:
    activate_validator_num: int128 = 0
    all_validator_slots_num: int128 = self.num_validators + self.empty_slots_stack_top

    # TODO: any better way to iterate the mapping?
    for i in range(1024):
        if i >= all_validator_slots_num:
            break
        if not not self.validators[i].addr:
            activate_validator_num += 1
    return activate_validator_num + self.empty_slots_stack_top


# Adds a validator to the validator set, with the validator's size being the msg.value
# (ie. amount of ETH deposited) in the function call. Returns the validator index.
@public
@payable
def deposit() -> int128:
    validator_addr: address = msg.sender
    assert not self.is_validator_deposited[validator_addr]
    assert msg.value == self.deposit_size
    # find the empty slot index in validators set
    index: int128 = self.num_validators
    if not self.is_stack_empty():
        index = self.stack_pop()        
    self.validators[index] = {
        deposit: msg.value,
        addr: validator_addr,
    }
    self.num_validators += 1
    self.is_validator_deposited[validator_addr] = True

    log.Deposit(index, validator_addr, msg.value)

    return index


# Verifies that `msg.sender == validators[validator_index].addr`. if it is removes the validator
# from the validator set and refunds the deposited ETH.
@public
@payable
def withdraw(validator_index: int128) -> bool:
    validator_addr: address = self.validators[validator_index].addr
    validator_deposit: wei_value = self.validators[validator_index].deposit
    assert msg.sender == validator_addr
    self.is_validator_deposited[validator_addr] = False
    self.validators[validator_index] = {
        deposit: 0,
        addr: None,
    }
    self.stack_push(validator_index)
    self.num_validators -= 1

    send(validator_addr, validator_deposit)

    log.Withdraw(validator_index, validator_addr, validator_deposit)

    return True


# Helper function to get collation header score
@public
@constant
def get_collation_header_score(shard_id: int128, collation_header_hash: bytes32) -> int128:
    collation_score: int128 = convert(
        uint256_mod(
            convert(self.collation_headers[shard_id][collation_header_hash], 'uint256'),
            # Mod 2^48, i.e., extract right most 6 bytes
            convert(281474976710656, 'uint256')
        ),
        'int128'
    )
    return collation_score


# Uses a block hash as a seed to pseudorandomly select a signer from the validator set.
# [TODO] Chance of being selected should be proportional to the validator's deposit.
# Should be able to return a value for the current period or any future period up to.
@public
@constant
def get_eligible_proposer(shard_id: int128, period: int128) -> address:
    assert period >= self.lookahead_periods
    assert (period - self.lookahead_periods) * self.period_length < block.number
    assert self.num_validators > 0
    return self.validators[
        convert(
            uint256_mod(
                convert(
                        sha3(
                            concat(
                                # TODO: should check further if this can be further optimized or not
                                #       e.g. be able to get the proposer of one period earlier
                                blockhash((period - self.lookahead_periods) * self.period_length),
                                convert(shard_id, 'bytes32'),
                            )
                        ),
                        'uint256'
                ),
                convert(self.get_validators_max_index(), 'uint256')
            ),
            'int128'
        )
    ].addr


# Attempts to process a collation header, returns True on success, reverts on failure.
@public
def add_header(
        shard_id: int128,
        expected_period_number: int128,
        period_start_prevhash: bytes32,
        parent_hash: bytes32,
        transaction_root: bytes32,
        collation_coinbase: address,  # TODO: cannot be named `coinbase` since it is reserved
        state_root: bytes32,
        receipt_root: bytes32,
        collation_number: int128) -> bool:  # TODO: cannot be named `number` since it is reserved

    # Check if the header is valid
    assert (shard_id >= 0) and (shard_id < self.shard_count)
    assert block.number >= self.period_length
    assert expected_period_number == floor(block.number / self.period_length)
    assert period_start_prevhash == blockhash(expected_period_number * self.period_length - 1)
    # Check if only one collation in one period perd shard
    assert self.period_head[shard_id] < expected_period_number

    # Check if this header already exists
    header_bytes: bytes <= 288 = concat(
        convert(shard_id, 'bytes32'),
        convert(expected_period_number, 'bytes32'),
        period_start_prevhash,
        parent_hash,
        transaction_root,
        convert(collation_coinbase, 'bytes32'),
        state_root,
        receipt_root,
        convert(collation_number, 'bytes32'),
    )
    entire_header_hash: bytes32 = convert(
        uint256_mod(
            convert(sha3(header_bytes), 'uint256'),
            # Mod 2^208, i.e., extract right most 26 bytes
            convert(411376139330301510538742295639337626245683966408394965837152256, 'uint256')
        ),
        'bytes32'
    )
    
    # Check if parent header exists.
    # If it exist, check that it's score is greater than 0.
    parent_collation_score: int128 = self.get_collation_header_score(
        shard_id,
        parent_hash,
    )
    if not not parent_hash:
        assert parent_collation_score > 0

    # Check that there's eligible proposer in this period
    # and msg.sender is also the eligible proposer
    validator_addr: address = self.get_eligible_proposer(
        shard_id,
        floor(block.number / self.period_length)
    )
    assert not not validator_addr
    assert msg.sender == validator_addr

    # Check score == collation_number
    _score: int128 = parent_collation_score + 1
    assert collation_number == _score

    # Add the header
    self.collation_headers[shard_id][entire_header_hash] = convert(
        uint256_add(
            uint256_mul(
                convert(parent_hash, 'uint256'),
                # Multiplied by 2^48, i.e., left shift 6 bytes
                convert(281474976710656, 'uint256')
            ),
            uint256_mod(
                convert(_score, 'uint256'),
                # Mod 2^48, i.e. confine it's range to 6 bytes
                convert(281474976710656, 'uint256')
            ),
        ),
        'bytes32'
    )

    # Update the latest period number
    self.period_head[shard_id] = expected_period_number

    # Determine the head
    is_new_head: bool = False
    shard_head_score: int128 = self.get_collation_header_score(
        shard_id,
        self.shard_head[shard_id],
    )
    if _score > shard_head_score:
        self.shard_head[shard_id] = entire_header_hash
        is_new_head = True

    # Emit log
    log.CollationAdded(
        shard_id,
        expected_period_number,
        period_start_prevhash,
        parent_hash,
        transaction_root,
        collation_coinbase,
        state_root,
        receipt_root,
        collation_number,
        is_new_head,
        _score,
    )

    return True


# Returns the gas limit that collations can currently have (by default make
# this function always answer 10 million).
@public
@constant
def get_collation_gas_limit() -> int128:
    return 10000000


# Records a request to deposit msg.value ETH to address to in shard shard_id
# during a future collation. Saves a `receipt ID` for this request,
# also saving `msg.sender`, `msg.value`, `to`, `shard_id`, `startgas`,
# `gasprice`, and `data`.
@public
@payable
def tx_to_shard(
        to: address,
        shard_id: int128,
        tx_startgas: int128,
        tx_gasprice: int128,
        data: bytes <= 4096) -> int128:
    self.receipts[self.num_receipts] = {
        shard_id: shard_id,
        tx_startgas: tx_startgas,
        tx_gasprice: tx_gasprice,
        value: msg.value,
        sender: msg.sender,
        to: to,
        data: data,
    }
    receipt_id: int128 = self.num_receipts
    self.num_receipts += 1

    # TODO: determine the signature of the log TxToShard
    raw_log(
        [
            sha3("tx_to_shard(address,int128,int128,int128,bytes4096)"),
            convert(to, 'bytes32'),
            convert(shard_id, 'bytes32'),
        ],
        concat('', convert(receipt_id, 'bytes32')),
    )

    return receipt_id


# Updates the tx_gasprice in receipt receipt_id, and returns True on success.
@public
@payable
def update_gasprice(receipt_id: int128, tx_gasprice: int128) -> bool:
    assert self.receipts[receipt_id].sender == msg.sender
    self.receipts[receipt_id].tx_gasprice = tx_gasprice
    return True
