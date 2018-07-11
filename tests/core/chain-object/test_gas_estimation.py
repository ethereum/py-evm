import pytest

from eth.estimators.gas import binary_gas_search_1000_tolerance
from eth.utils.address import force_bytes_to_address

from tests.core.helpers import (
    fill_block,
    new_transaction,
)


ADDRESS_2 = b'\0' * 19 + b'\x02'

ADDR_1010 = force_bytes_to_address(b'\x10\x10')


@pytest.fixture
def chain(chain_without_block_validation):
    return chain_without_block_validation


@pytest.mark.parametrize(
    'should_sign_tx', (True, False),
)
@pytest.mark.parametrize(
    'data, gas_estimator, to, on_pending, expected',
    (
        (b'', None, ADDR_1010, True, 21000),
        (b'', None, ADDR_1010, False, 21000),
        (b'\xff' * 10, None, ADDR_1010, True, 21680),
        (b'\xff' * 10, None, ADDR_1010, False, 21680),
        # sha3 precompile
        (b'\xff' * 32, None, ADDRESS_2, True, 35381),
        (b'\xff' * 32, None, ADDRESS_2, False, 35369),
        (b'\xff' * 320, None, ADDRESS_2, True, 54888),
        # 1000_tolerance binary search
        (b'\xff' * 32, binary_gas_search_1000_tolerance, ADDRESS_2, True, 23938),
    ),
    ids=[
        'simple default pending',
        'simple default',
        '10 bytes default pending',
        '10 bytes default',
        'sha3 precompile 32 bytes default pending',
        'sha3 precompile 32 bytes default',
        'sha3 precompile 320 bytes default pending',
        'sha3 precompile 32 bytes 1000_tolerance binary pending',
    ],
)
def test_estimate_gas(
        chain,
        data,
        gas_estimator,
        to,
        on_pending,
        expected,
        funded_address,
        funded_address_private_key,
        should_sign_tx):
    if gas_estimator:
        chain.gas_estimator = gas_estimator
    vm = chain.get_vm()
    amount = 100
    from_ = funded_address

    tx_params = dict(
        vm=vm,
        from_=from_,
        to=to,
        amount=amount,
        data=data
    )

    # either make a signed or unsigned transaction
    if should_sign_tx:
        tx = new_transaction(private_key=funded_address_private_key, **tx_params)
    else:
        tx = new_transaction(**tx_params)

    if on_pending:
        # estimate on *pending* block
        pending_header = chain.create_header_from_parent(chain.get_canonical_head())
        assert chain.estimate_gas(tx, pending_header) == expected
    else:
        # estimates on top of *latest* block
        assert chain.estimate_gas(tx) == expected
        # these are long, so now that we know the exact numbers let's skip the repeat test
        # assert chain.estimate_gas(tx, chain.get_canonical_head()) == expected


def test_estimate_gas_on_full_block(chain, funded_address_private_key, funded_address):

    def mk_estimation_txn(chain, from_, from_key, data):
        vm = chain.get_vm()
        tx_params = dict(
            from_=from_,
            to=ADDR_1010,
            amount=200,
            private_key=from_key,
            gas=chain.header.gas_limit,
            data=data
        )
        return new_transaction(vm, **tx_params)

    from_ = funded_address
    from_key = funded_address_private_key
    garbage_data = b"""
        fill up the block much faster because this transaction contains a bunch of extra
        garbage_data, which doesn't add to execution time, just the gas costs
    """ * 30
    gas = 375000

    # fill the canonical head
    fill_block(chain, from_, from_key, gas, garbage_data)
    chain.import_block(chain.get_vm().block)

    # build a transaction to estimate gas for
    next_canonical_tx = mk_estimation_txn(chain, from_, from_key, data=garbage_data * 2)

    assert chain.estimate_gas(next_canonical_tx) == 722760

    # fill the pending block
    fill_block(chain, from_, from_key, gas, garbage_data)

    # build a transaction to estimate gas for
    next_pending_tx = mk_estimation_txn(chain, from_, from_key, data=garbage_data * 2)

    assert chain.estimate_gas(next_pending_tx, chain.header) == 722760
