from eth_keys import keys
from eth_utils import decode_hex

from tests.trinity.core.integration_test_helpers import FUNDED_ACCT, load_mining_chain

RECEIVER = keys.PrivateKey(
    decode_hex("b71c71a67e1177ad4e901695e1b4b9ee17ae16c6668d313eac2f96dbcda3f291"))


def build_pow_fixture(write_db, num_blocks=20):
    chain = load_mining_chain(write_db)
    for i in range(num_blocks):
        tx = chain.create_unsigned_transaction(
            nonce=i,
            gas_price=1234,
            gas=123400,
            to=RECEIVER.public_key.to_canonical_address(),
            value=i,
            data=b'',
        )
        chain.apply_transaction(tx.as_signed_transaction(FUNDED_ACCT))
        chain.mine_block()
    return chain.chaindb
