from eth_utils import (
    hexstr_if_str,
    to_bytes,
    to_wei,
)
import pytest

from eth._utils.address import (
    generate_contract_address,
)
from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from eth.exceptions import (
    OutOfGas,
)
from eth.tools.factories.transaction import (
    new_transaction,
)
from eth.vm import (
    opcode_values,
)
from eth.vm.forks.spurious_dragon.computation import (
    SpuriousDragonComputation,
)
from eth.vm.forks.spurious_dragon.constants import (
    EIP170_CODE_SIZE_LIMIT,
)
from eth.vm.message import (
    Message,
)


def assemble(*codes):
    return b"".join(hexstr_if_str(to_bytes, element) for element in codes)


@pytest.mark.parametrize(
    "code_len",
    [
        0,
        1,
        0xFF,
        EIP170_CODE_SIZE_LIMIT - 1,
        EIP170_CODE_SIZE_LIMIT,
        EIP170_CODE_SIZE_LIMIT + 1,
        EIP170_CODE_SIZE_LIMIT + 0x10000,
    ],
)
def test_contract_code_size_limit(
    chain_without_block_validation, funded_address, funded_address_private_key, code_len
):
    ZERO_OPCODE_32 = b"\x00" * 32
    CODE_LEN_OPCODE = code_len.to_bytes(32, byteorder="big")

    deploy_contract_opcodes = assemble(
        # PUSH32, value, PUSH32, offset, MSTORE
        opcode_values.PUSH32,
        ZERO_OPCODE_32,
        opcode_values.PUSH32,
        ZERO_OPCODE_32,
        opcode_values.MSTORE,
        # PUSH32, length, PUSH32, offset, RETURN
        opcode_values.PUSH32,
        CODE_LEN_OPCODE,
        opcode_values.PUSH32,
        ZERO_OPCODE_32,
        opcode_values.RETURN,
    )

    vm = chain_without_block_validation.get_vm()

    message = Message(
        to=CREATE_CONTRACT_ADDRESS,
        sender=funded_address,
        create_address=generate_contract_address(
            funded_address, vm.state.get_nonce(funded_address)
        ),
        value=0,
        data=b"",
        code=deploy_contract_opcodes,
        gas=to_wei(1, "ether"),
    )

    transaction = new_transaction(
        vm=vm,
        from_=funded_address,
        to=CREATE_CONTRACT_ADDRESS,
        private_key=funded_address_private_key,
        data=deploy_contract_opcodes,
    )

    computation = vm.state.get_transaction_executor().build_computation(
        message,
        transaction,
    )

    # EIP-170 apply after the SpuriousDragon fork.
    if (
        issubclass(computation.__class__, SpuriousDragonComputation)
        and code_len > EIP170_CODE_SIZE_LIMIT
    ):
        assert isinstance(computation.error, OutOfGas)
    else:
        assert computation.is_success
