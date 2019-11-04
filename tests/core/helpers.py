import sys

import pytest

from eth_utils import (
    decode_hex,
    ValidationError,
)

from eth.chains.base import MiningChain
from eth.tools.factories.transaction import new_transaction

greater_equal_python36 = pytest.mark.skipif(
    sys.version_info < (3, 6),
    reason="requires python3.6 or higher"
)


def fill_block(chain, from_, key, gas, data):
    if not isinstance(chain, MiningChain):
        pytest.skip("Cannot fill block automatically unless using a MiningChain")
        return

    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100

    vm = chain.get_vm()
    assert vm.get_header().gas_used == 0

    while True:
        tx = new_transaction(chain.get_vm(), from_, recipient, amount, key, gas=gas, data=data)
        try:
            chain.apply_transaction(tx)
        except ValidationError as exc:
            if str(exc).startswith("Transaction exceeds gas limit"):
                break
            else:
                raise exc

    assert chain.get_vm().get_block().header.gas_used > 0
