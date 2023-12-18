from eth_utils import (
    ValidationError,
    decode_hex,
)
import pytest

from eth.chains.base import (
    MiningChain,
)
from eth.tools.factories.transaction import (
    new_transaction,
)


def fill_block(chain, from_, key, gas, data):
    if not isinstance(chain, MiningChain):
        pytest.skip("Cannot fill block automatically unless using a MiningChain")
        return

    recipient = decode_hex("0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c")
    amount = 100

    vm = chain.get_vm()
    assert vm.get_header().gas_used == 0

    while True:
        tx = new_transaction(
            chain.get_vm(), from_, recipient, amount, key, gas=gas, data=data
        )
        try:
            chain.apply_transaction(tx)
        except ValidationError as exc:
            if str(exc).startswith("Transaction exceeds gas limit"):
                break
            else:
                raise exc
        else:
            new_header = chain.get_vm().get_block().header
            assert new_header.gas_used > 0
            assert new_header.gas_used <= new_header.gas_limit

    assert chain.get_vm().get_block().header.gas_used > 0
