# Information about validators
validators: public({
    # Amount of wei the validator holds
    deposit: wei_value,
    # The address which the validator's signatures must verify to (to be later replaced with validation code)
    validation_code_addr: address,
    # Addess to withdraw to
    return_addr: address,
    # The cycle number which the validator would be included after
    # Will be [DEPRECATED] for stateless client
    cycle: num,
}[num])

# Number of validators
num_validators: public(num)

# Collation headers
collation_headers: public({
    parent_collation_hash: bytes32,
    score: num,
}[bytes32][num])

# Receipt data
receipts: public({
    shard_id: num,
    tx_startgas: num,
    tx_gasprice: num,
    value: wei_value,
    sender: address,
    to: address,
    data: bytes <= 4096
}[num])

# Current head of each shard
shard_head: public(bytes32[num])

# Number of receipts
num_receipts: num

# Indexs of empty slots caused by the function `withdraw`
empty_slots_stack: num[num]

# The top index of the stack in empty_slots_stack
empty_slots_stack_top: num

# Gas limit of the signature validation code
sig_gas_limit: num

# Is a valcode addr deposited now?
is_valcode_deposited: public(bool[address])

# Log the latest period number of the shard
period_head: public(num[num])

# Collations with score
# [shard_id][score][num_collation] -> collation_hash
collations_with_score: public(bytes32[num][num][num])

# Number of collations_with_score
num_collations_with_score: public(num[num][num])


# Configuration Parameter

# The exact deposit size which you have to deposit to become a validator
deposit_size: wei_value

# Any given validator randomly gets allocated to some number of shards every SHUFFLING_CYCLE
# Will be [DEPRECATED] for stateless client
shuffling_cycle_length: num

# Number of blocks in one period
period_length: num

# Number of validators of each cycle
# will be [DEPRECATED] for stateless client
num_validators_per_cycle: num

# Number of shards
shard_count: num

# Number of periods ahead of current period, which the contract
# is able to return the collator of that period
lookahead_periods: num


# Constant

# The address of sighasher contract
sighasher_addr: address


# Events
# CollationAdded(indexed uint256 shard, bytes collationHeader, bool isNewHead, uint256 score)

@public
def __init__():
    self.num_validators = 0
    self.empty_slots_stack_top = 0
    # 10 ** 20 wei = 100 ETH
    self.deposit_size = 100000000000000000000
    self.shuffling_cycle_length = 25  # FIXME: just modified temporarily for test
    self.sig_gas_limit = 40000
    self.period_length = 5
    self.num_validators_per_cycle = 100
    self.shard_count = 100
    self.lookahead_periods = 4
    self.sighasher_addr = 0xDFFD41E18F04Ad8810c83B14FD1426a82E625A7D


# Checks if empty_slots_stack_top is empty
@internal
def is_stack_empty() -> bool:
    return (self.empty_slots_stack_top == 0)


# Pushes one num to empty_slots_stack
@internal
def stack_push(index: num):
    self.empty_slots_stack[self.empty_slots_stack_top] = index
    self.empty_slots_stack_top += 1


# Pops one num out of empty_slots_stack
@internal
def stack_pop() -> num:
    if self.is_stack_empty():
        return -1
    self.empty_slots_stack_top -= 1
    return self.empty_slots_stack[self.empty_slots_stack_top]


# Returns the current maximum index for validators mapping
@internal
def get_validators_max_index() -> num:
    zero_addr = 0x0000000000000000000000000000000000000000
    activate_validator_num = 0
    all_validator_slots_num = self.num_validators + self.empty_slots_stack_top

    # TODO: any better way to iterate the mapping?
    for i in range(1024):
        if i >= all_validator_slots_num:
            break
        if self.validators[i].validation_code_addr != zero_addr:
            activate_validator_num += 1
    return activate_validator_num + self.empty_slots_stack_top


# Adds a validator to the validator set, with the validator's size being the msg.value
# (ie. amount of ETH deposited) in the function call. Returns the validator index.
# validationCodeAddr stores the address of the validation code; the function fails
# if this address's code has not been purity-verified.
@public
@payable
def deposit(validation_code_addr: address, return_addr: address) -> num:
    assert not self.is_valcode_deposited[validation_code_addr]
    assert msg.value == self.deposit_size
    # find the empty slot index in validators set
    if not self.is_stack_empty():
        index = self.stack_pop()
    else:
        index = self.num_validators
    self.validators[index] = {
        deposit: msg.value,
        validation_code_addr: validation_code_addr,
        return_addr: return_addr,
        cycle: 0
    }
    self.num_validators += 1
    self.is_valcode_deposited[validation_code_addr] = True

    raw_log(
        [sha3("deposit(address,address)"), as_bytes32(validation_code_addr)],
        concat('', as_bytes32(index))
    )

    return index


# Verifies that the signature is correct (ie. a call with 200000 gas, validationCodeAddr as
# destination, 0 value and sha3("withdraw") + sig as data returns 1), and if it is removes
# the validator from the validator set and refunds the deposited ETH.
@public
def withdraw(validator_index: num, sig: bytes <= 4096) -> bool:
    msg_hash = sha3("withdraw")
    result = (extract32(raw_call(self.validators[validator_index].validation_code_addr, concat(msg_hash, sig), gas=self.sig_gas_limit, outsize=32), 0) == as_bytes32(1))
    if result:
        send(self.validators[validator_index].return_addr, self.validators[validator_index].deposit)
        self.is_valcode_deposited[self.validators[validator_index].validation_code_addr] = False
        self.validators[validator_index] = {
            deposit: 0,
            validation_code_addr: None,
            return_addr: None,
            cycle: 0
        }
        self.stack_push(validator_index)
        self.num_validators -= 1
        raw_log(
            [sha3("withdraw(int128,bytes4096)")],
            concat('', as_bytes32(validator_index)),
        )
    return result


# Will be [DEPRECATED] for stateless client
@public
@constant
def sample(shard_id: num) -> address:
    cycle = floor(decimal(block.number / self.shuffling_cycle_length))
    cycle_start_block_number = cycle * self.shuffling_cycle_length - 1
    if cycle_start_block_number < 0:
        cycle_start_block_number = 0
    cycle_seed = blockhash(cycle_start_block_number)
    # originally, error occurs when block.number <= 4 because
    # `seed_block_number` becomes negative in these cases.
    # Now, just reject the cases when block.number <= 4
    assert block.number >= self.period_length
    seed = blockhash(block.number - (block.number % self.period_length) - 1)
    index_in_subset = num256_mod(as_num256(sha3(concat(seed, as_bytes32(shard_id)))),
                                 as_num256(self.num_validators_per_cycle))
    validator_index = num256_mod(as_num256(sha3(concat(cycle_seed, as_bytes32(shard_id), as_bytes32(index_in_subset)))),
                                 as_num256(self.get_validators_max_index()))
    if self.validators[as_num128(validator_index)].cycle > cycle:
        return 0x0000000000000000000000000000000000000000
    else:
        return self.validators[as_num128(validator_index)].validation_code_addr


# Uses a block hash as a seed to pseudorandomly select a signer from the validator set.
# [TODO] Chance of being selected should be proportional to the validator's deposit.
# Should be able to return a value for the current period or any future period up to.
@public
@constant
def get_eligible_proposer(shard_id: num, period: num) -> address:
    assert period >= self.lookahead_periods
    assert (period - self.lookahead_periods) * self.period_length < block.number
    assert self.num_validators > 0
    return self.validators[
        as_num128(
            num256_mod(
                as_num256(
                    sha3(
                        concat(
                            blockhash((period - self.lookahead_periods) * self.period_length),
                            as_bytes32(shard_id)
                        )
                    )
                ),
                as_num256(self.get_validators_max_index())
            )
        )
    ].validation_code_addr


# Get all possible shard ids that the given valcode_addr may be sampled in the current cycle
# Will be [DEPRECATED] for stateless client
@public
@constant
def get_shard_list(valcode_addr: address) -> bool[100]:
    shard_list: bool[100]
    cycle = floor(decimal(block.number / self.shuffling_cycle_length))
    cycle_start_block_number = cycle * self.shuffling_cycle_length - 1
    if cycle_start_block_number < 0:
        cycle_start_block_number = 0
    cycle_seed = blockhash(cycle_start_block_number)
    validators_max_index = self.get_validators_max_index()
    if self.num_validators != 0:
        for shard_id in range(100):
            shard_list[shard_id] = False
            # range(shard_count): , possible shard_id
            for possible_index_in_subset in range(100):
                # range(num_validators_per_cycle): possible index_in_subset
                validator_index = num256_mod(
                    as_num256(
                        sha3(
                            concat(
                                cycle_seed,
                                as_bytes32(shard_id),
                                as_bytes32(possible_index_in_subset))
                            )
                    ),
                    as_num256(validators_max_index)
                )
                if valcode_addr == self.validators[as_num128(validator_index)].validation_code_addr:
                    shard_list[shard_id] = True
                    break
    return shard_list


# emit a log which is equivalent to
# CollationAdded: __log__({shard_id: indexed(num), collation_header: bytes <= 4096, is_new_head: bool, score: num})
# TODO: should be replaced by `log.CollationAdded`
@internal
def emit_collation_added(shard_id: num, collation_header: bytes <= 4096, is_new_head: bool, score: num):
    if is_new_head:
        new_head_in_num = 1
    else:
        new_head_in_num = 0
    raw_log(
        [
            sha3("CollationAdded(int128,bytes4096,bool,int128)"),
            as_bytes32(shard_id),
        ],
        concat(
            collation_header,
            as_bytes32(new_head_in_num),
            as_bytes32(score),
        )
    )


# Attempts to process a collation header, returns True on success, reverts on failure.
@public
def add_header(header: bytes <= 4096) -> bool:
    zero_addr = 0x0000000000000000000000000000000000000000

    values = RLPList(header, [num, num, bytes32, bytes32, bytes32, address, bytes32, bytes32, num, bytes])
    shard_id = values[0]
    expected_period_number = values[1]
    period_start_prevhash = values[2]
    parent_collation_hash = values[3]
    tx_list_root = values[4]
    collation_coinbase = values[5]
    post_state_root = values[6]
    receipt_root = values[7]
    collation_number = values[8]
    sig = values[9]

    # Check if the header is valid
    assert (shard_id >= 0) and (shard_id < self.shard_count)
    assert block.number >= self.period_length
    assert expected_period_number == floor(decimal(block.number / self.period_length))
    assert period_start_prevhash == blockhash(expected_period_number * self.period_length - 1)

    # Check if this header already exists
    entire_header_hash = sha3(header)
    assert entire_header_hash != as_bytes32(0)
    assert self.collation_headers[shard_id][entire_header_hash].score == 0
    # Check whether the parent exists.
    # if (parent_collation_hash == 0), i.e., is the genesis,
    # then there is no need to check.
    if parent_collation_hash != as_bytes32(0):
        assert (parent_collation_hash == as_bytes32(0)) or (self.collation_headers[shard_id][parent_collation_hash].score > 0)
    # Check if only one colllation in one period
    assert self.period_head[shard_id] < expected_period_number

    # Check the signature with validation_code_addr
    collator_valcode_addr = self.get_eligible_proposer(shard_id, block.number / self.period_length)
    if collator_valcode_addr == zero_addr:
        return False
    sighash = extract32(raw_call(self.sighasher_addr, header, gas=200000, outsize=32), 0)
    assert extract32(raw_call(collator_valcode_addr, concat(sighash, sig), gas=self.sig_gas_limit, outsize=32), 0) == as_bytes32(1)

    # Check score == collation_number
    _score = self.collation_headers[shard_id][parent_collation_hash].score + 1
    assert collation_number == _score

    # Add the header
    self.collation_headers[shard_id][entire_header_hash] = {
        parent_collation_hash: parent_collation_hash,
        score: _score
    }

    # Update collations_with_score
    self.collations_with_score[shard_id][_score][self.num_collations_with_score[shard_id][_score]] = entire_header_hash
    self.num_collations_with_score[shard_id][_score] = self.num_collations_with_score[shard_id][_score] + 1

    # Update the latest period number
    self.period_head[shard_id] = expected_period_number

    # Determine the head
    is_new_head = False
    if _score > self.collation_headers[shard_id][self.shard_head[shard_id]].score:
        previous_head_hash = self.shard_head[shard_id]
        self.shard_head[shard_id] = entire_header_hash
        # only when `change_head` happens due to the fork, it is a new head
        if previous_head_hash != parent_collation_hash:
            is_new_head = True

    # Emit log
    self.emit_collation_added(shard_id, header, is_new_head, _score)

    return True


# Returns the block hash of block `PERIOD_LENGTH * expected_period_number - 1`
@public
@constant
def get_period_start_prevhash(expected_period_number: num) -> bytes32:
    block_number = expected_period_number * self.period_length - 1
    assert block.number > block_number
    return blockhash(block_number)


# Returns the gas limit that collations can currently have (by default make
# this function always answer 10 million).
@public
@constant
def get_collation_gas_limit() -> num:
    return 10000000


# Records a request to deposit msg.value ETH to address to in shard shard_id
# during a future collation. Saves a `receipt ID` for this request,
# also saving `msg.sender`, `msg.value`, `to`, `shard_id`, `startgas`,
# `gasprice`, and `data`.
@public
@payable
def tx_to_shard(to: address, shard_id: num, tx_startgas: num, tx_gasprice: num, data: bytes <= 4096) -> num:
    self.receipts[self.num_receipts] = {
        shard_id: shard_id,
        tx_startgas: tx_startgas,
        tx_gasprice: tx_gasprice,
        value: msg.value,
        sender: msg.sender,
        to: to,
        data: data
    }
    receipt_id = self.num_receipts
    self.num_receipts += 1

    raw_log(
        [sha3("tx_to_shard()"), as_bytes32(to), as_bytes32(shard_id)],
        concat('', as_bytes32(receipt_id))
    )

    return receipt_id


# Updates the tx_gasprice in receipt receipt_id, and returns True on success.
@public
@payable
def update_gasprice(receipt_id: num, tx_gasprice: num) -> bool:
    assert self.receipts[receipt_id].sender == msg.sender
    self.receipts[receipt_id].tx_gasprice = tx_gasprice
    return True
