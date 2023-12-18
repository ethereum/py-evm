# test computation class behavior across VMs
from eth_typing import (
    Address,
)
from eth_utils import (
    decode_hex,
)
import pytest

from eth import (
    constants,
)
from eth.chains.base import (
    MiningChain,
)
from eth.chains.mainnet import (
    MINING_MAINNET_VMS,
)
from eth.consensus import (
    NoProofConsensus,
)
from eth.exceptions import (
    InvalidInstruction,
)


def _configure_mining_chain(starting_vm, vm_under_test):
    return MiningChain.configure(
        __name__="AllVMs",
        vm_configuration=(
            (
                constants.GENESIS_BLOCK_NUMBER,
                starting_vm.configure(consensus_class=NoProofConsensus),
            ),
            (
                constants.GENESIS_BLOCK_NUMBER + 1,
                vm_under_test.configure(consensus_class=NoProofConsensus),
            ),
        ),
        chain_id=1337,
    )


# CREATE, RETURNDATASIZE, and RETURNDATACOPY opcodes not added until Byzantium
@pytest.fixture(params=MINING_MAINNET_VMS[4:])
def byzantium_plus_miner(request, base_db, genesis_state):
    byzantium_vm = MINING_MAINNET_VMS[4]
    vm_under_test = request.param

    klass = _configure_mining_chain(byzantium_vm, vm_under_test)
    header_fields = dict(
        difficulty=1,
        gas_limit=100000,  # arbitrary, just enough for testing
    )
    return klass.from_genesis(base_db, header_fields, genesis_state)


@pytest.mark.parametrize(
    "code",
    (
        # generate some return data, then call CREATE (third-to-last opcode - 0xf0)
        decode_hex(
            "0x5b595958333d5859858585858585858585f195858585858585858485858585f195858585858585f1f03d30"  # noqa: E501
        ),
        # generate some return data, then call CREATE2 (third-to-last opcode - 0xf5)
        decode_hex(
            "0x5b595958333d5859858585858585858585f195858585858585858485858585f195858585858585f1f53d30"  # noqa: E501
        ),
    ),
)
def test_CREATE_and_CREATE2_resets_return_data_if_account_has_insufficient_funds(
    byzantium_plus_miner,
    canonical_address_a,
    transaction_context,
    code,
):
    chain = byzantium_plus_miner
    vm = chain.get_vm()
    state = vm.state

    assert state.get_balance(canonical_address_a) == 0

    computation = vm.execute_bytecode(
        origin=canonical_address_a,
        to=canonical_address_a,
        sender=Address(
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x12\x34"  # noqa: E501
        ),
        value=0,
        code=code,
        data=code,
        gas=40000,
        gas_price=1,
    )

    if computation.is_error:
        assert isinstance(computation.error, InvalidInstruction)
        # only test CREATE case for byzantium as the CREATE2 opcode (0xf5)
        # was not yet introduced
        assert vm.fork == "byzantium"
        assert "0xf5" in repr(computation.error).lower()

    else:
        # We provide 40000 gas and a simple create uses 32000 gas. This test doesn't
        # particularly care (and isn't testing for) the exact gas, we just want to make
        # sure not all the gas is burned since if, say, a VMError were to be raised it
        # would burn all the gas (burns_gas = True).
        assert 34000 < computation.get_gas_used() < 39000
        assert computation.return_data == b""
