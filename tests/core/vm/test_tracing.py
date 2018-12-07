
import pytest

from eth_utils import decode_hex

from eth.vm.tracing import StructTracer

from tests.core.helpers import (
    new_transaction,
)


@pytest.fixture
def chain(chain_without_block_validation):
    return chain_without_block_validation


def test_apply_transaction(
        chain,
        funded_address,
        funded_address_private_key,
        funded_address_initial_balance):
    vm = chain.get_vm()
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = funded_address
    tx = new_transaction(vm, from_, recipient, amount, funded_address_private_key)
    tracer = StructTracer()
    new_header, _, computation = vm.apply_transaction(vm.block.header, tx, tracer=tracer)

    assert tracer.result.error is (computation.error is not None)
    assert computation.output is tracer.result.output
    assert tracer.result.gas == computation.get_gas_used()
    assert len(tracer.result.logs) == 0
