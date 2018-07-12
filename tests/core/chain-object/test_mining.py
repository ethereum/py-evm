from eth_keys import keys
from eth_utils import decode_hex

from eth import constants
from eth.chains.base import (
    MiningChain,
)
from eth.db.backends.memory import MemoryDB
from eth.vm.forks.frontier import _PoWMiningVM


class PowMiningChain(MiningChain):
    vm_configuration = ((0, _PoWMiningVM),)
    network_id = 999


def test_pow_mining():
    sender = keys.PrivateKey(
        decode_hex("49a7b37aa6f6645917e7b807e9d1c00d4fa71f18343b0d4122a4d2df64dd6fee"))
    receiver = keys.PrivateKey(
        decode_hex("b71c71a67e1177ad4e901695e1b4b9ee17ae16c6668d313eac2f96dbcda3f291"))
    genesis_params = {
        'parent_hash': constants.GENESIS_PARENT_HASH,
        'uncles_hash': constants.EMPTY_UNCLE_HASH,
        'coinbase': constants.ZERO_ADDRESS,
        'transaction_root': constants.BLANK_ROOT_HASH,
        'receipt_root': constants.BLANK_ROOT_HASH,
        'bloom': 0,
        'difficulty': 5,
        'block_number': constants.GENESIS_BLOCK_NUMBER,
        'gas_limit': constants.GENESIS_GAS_LIMIT,
        'gas_used': 0,
        'timestamp': 1514764800,
        'extra_data': constants.GENESIS_EXTRA_DATA,
        'nonce': constants.GENESIS_NONCE
    }
    state = {
        sender.public_key.to_canonical_address(): {
            "balance": 100000000000000000,
            "code": b"",
            "nonce": 0,
            "storage": {}
        }
    }
    chain = PowMiningChain.from_genesis(MemoryDB(), genesis_params, state)
    for i in range(10):
        tx = chain.create_unsigned_transaction(
            nonce=i,
            gas_price=1234,
            gas=1234000,
            to=receiver.public_key.to_canonical_address(),
            value=i,
            data=b'',
        )
        chain.apply_transaction(tx.as_signed_transaction(sender))
        block = chain.mine_block()
        assert block.number == i + 1
        assert chain.header.block_number == i + 2
