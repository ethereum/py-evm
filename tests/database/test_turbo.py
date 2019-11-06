"Test that we can read from non-canonical states by looking at block diffs"
import pytest

from eth.db.turbo import TurboDatabase

from tests.core.helpers import (
    new_transaction,
)


@pytest.fixture
def chain(chain_without_block_validation):
    # make things a little less verbose
    return chain_without_block_validation


def test_read_older_state(chain, funded_address, funded_address_private_key):
    # Add two blocks to the chain.
    # Check that the turbodb has the newest state
    # Open a TurboDatabase from the older state and check that you get the correct result
    base_db = chain.chaindb.db
    ADDRESS = b'\x10' * 20

    def make_transaction_to(destination_address, amount, parent_header=None):
        return new_transaction(
            chain.get_vm(parent_header),
            funded_address,
            destination_address,
            data=b'',
            private_key=funded_address_private_key,
            amount=amount,
        )

    assert TurboDatabase._get_account(base_db, ADDRESS).balance == 0

    first_transaction = make_transaction_to(ADDRESS, 1000)
    first_new_block, _, _ = chain.build_block_with_transactions([first_transaction])
    first_imported_block, _, _ = chain.import_block(first_new_block)
    assert TurboDatabase._get_account(base_db, ADDRESS).balance == 1000
    assert TurboDatabase._get_account(base_db, funded_address).nonce == 1

    second_transaction = make_transaction_to(ADDRESS, 2000)
    second_new_block, _, _ = chain.build_block_with_transactions([second_transaction])
    second_imported_block, _, _ = chain.import_block(second_new_block)
    assert TurboDatabase._get_account(base_db, ADDRESS).balance == 3000
    assert TurboDatabase._get_account(base_db, funded_address).nonce == 2

    turbo = TurboDatabase(chain.chaindb, first_imported_block.header)
    assert turbo.get_account(ADDRESS).balance == 1000
    assert turbo.get_account(funded_address).nonce == 1
