
import pytest

from eth_utils import decode_hex, to_int

from eth.tools.builder.chain import api as b
from eth.vm.tracing import StructTracer
from eth.chains.base import Chain


CONTRACT_ADDRESS = decode_hex('0x1000000000000000000000000000000000000000')
# From `fixtures/VMTests/vmArithmetic/add0.json'
CONTRACT_CODE = decode_hex('0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7ff'
                           'fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff01600055'
                           )


@pytest.fixture(params=b.mainnet_fork_at_fns)
def chain(request, funded_address, funded_address_initial_balance):
    fork_at_fn = request.param
    return b.build(
        Chain,
        fork_at_fn(0),
        b.disable_pow_check(),
        b.genesis(
            params={'gas_limit': 3141592},
            state=(
                (funded_address, 'balance', funded_address_initial_balance),
                (CONTRACT_ADDRESS, 'code', CONTRACT_CODE),
            ),
        )
    )


def mk_transaction(
        vm,
        private_key,
        to,
        amount=0,
        gas_price=1,
        gas=100000,
        data=b''):
    """
    Create and return a transaction sending amount from <from_> to <to>.

    The transaction will be signed with the given private key.
    """
    nonce = vm.state.account_db.get_nonce(private_key.public_key.to_canonical_address())
    tx = vm.create_unsigned_transaction(
        nonce=nonce,
        gas_price=gas_price,
        gas=gas,
        to=to,
        value=amount,
        data=data,
    )
    return tx.as_signed_transaction(private_key)


def test_trace_simple_value_transfer(
        chain,
        funded_address_private_key):
    vm = chain.get_vm()
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    tx = mk_transaction(vm, funded_address_private_key, recipient, amount)
    tracer = StructTracer()
    _, _, computation = vm.apply_transaction(vm.block.header, tx, tracer=tracer)

    result = tracer.result

    assert result.error is (computation.error is not None)
    assert computation.output == result.output
    assert result.gas == computation.get_gas_used()
    assert len(result.logs) == 0


def test_trace_add0(
        chain,
        funded_address_private_key):
    vm = chain.get_vm()
    recipient = CONTRACT_ADDRESS
    tx = mk_transaction(vm, funded_address_private_key, recipient)
    tracer = StructTracer()
    _, _, computation = vm.apply_transaction(vm.block.header, tx, tracer=tracer)

    result = tracer.result

    assert result.error is False
    assert computation.output == b''
    assert result.gas == computation.get_gas_used()

    # Ensure that the actual opcodes are accurate
    expected_ops = ['PUSH32', 'PUSH32', 'ADD', 'PUSH1', 'SSTORE']
    actual_ops = [entry.op for entry in result.logs]
    assert actual_ops == expected_ops

    log_0, log_1, log_2, log_3, log_4 = result.logs
    expected_add_result = to_int(hexstr='0xffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
                                        'fffffffe')

    # Check expected stack size
    assert len(log_0.stack) == 0
    assert len(log_1.stack) == 1  # (left operand)
    assert len(log_2.stack) == 2  # (left operand, right operand)
    assert len(log_3.stack) == 1  # (add result)
    assert len(log_4.stack) == 2  # (add result, storage_slot)

    last_storage = result.logs[-1].storage
    assert 0 in last_storage
    assert last_storage[0] == expected_add_result
