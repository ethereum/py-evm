from eth_utils import (
    decode_hex,
    function_signature_to_4byte_selector,
    to_bytes,
)
from eth_utils.toolz import (
    assoc,
)
import pytest

from eth.exceptions import (
    InvalidInstruction,
    OutOfGas,
    Revert,
)
from eth.tools.factories.transaction import (
    new_transaction,
)
from eth.vm.forks import (
    ArrowGlacierVM,
    BerlinVM,
    ByzantiumVM,
    ConstantinopleVM,
    FrontierVM,
    GrayGlacierVM,
    HomesteadVM,
    IstanbulVM,
    LondonVM,
    MuirGlacierVM,
    PetersburgVM,
    SpuriousDragonVM,
    TangerineWhistleVM,
)


@pytest.fixture
def chain(chain_with_block_validation):
    return chain_with_block_validation


@pytest.fixture
def simple_contract_address():
    return b"\x88" * 20


@pytest.fixture
def genesis_state(base_genesis_state, simple_contract_address):
    """
    Includes runtime bytecode of compiled Solidity:

        pragma solidity ^0.4.24;

        contract GetValues {
            function getMeaningOfLife() public pure returns (uint256) {
                return 42;
            }
            function getGasPrice() public view returns (uint256) {
                return tx.gasprice;
            }
            function getBalance() public view returns (uint256) {
                return msg.sender.balance;
            }
            function doRevert() public pure {
                revert("always reverts");
            }
            function useLotsOfGas() public view {
                uint size;
                for (uint i = 0; i < 2**255; i++){
                    assembly {
                        size := extcodesize(0)
                    }
                }
            }
        }
    """
    return assoc(
        base_genesis_state,
        simple_contract_address,
        {
            "balance": 0,
            "nonce": 0,
            "code": decode_hex(
                "60806040526004361061006c5763ffffffff7c010000000000000000000000000000000000000000000000000000000060003504166312065fe08114610071578063455259cb14610098578063858af522146100ad57806395dd7a55146100c2578063afc874d2146100d9575b600080fd5b34801561007d57600080fd5b506100866100ee565b60408051918252519081900360200190f35b3480156100a457600080fd5b506100866100f3565b3480156100b957600080fd5b506100866100f7565b3480156100ce57600080fd5b506100d76100fc565b005b3480156100e557600080fd5b506100d7610139565b333190565b3a90565b602a90565b6000805b7f80000000000000000000000000000000000000000000000000000000000000008110156101355760003b9150600101610100565b5050565b604080517f08c379a000000000000000000000000000000000000000000000000000000000815260206004820152600e60248201527f616c776179732072657665727473000000000000000000000000000000000000604482015290519081900360640190fd00a165627a7a72305820645df686b4a16d5a69fc6d841fc9ad700528c14b35ca5629e11b154a9d3dff890029"  # noqa: E501
            ),
            "storage": {},
        },
    )


def uint256_to_bytes(uint):
    return to_bytes(uint).rjust(32, b"\0")


@pytest.mark.parametrize(
    "signature, gas_price, expected",
    (
        (
            "getMeaningOfLife()",
            10**10,  # In order to work with >=EIP-1559, minimum gas should be >1 gwei
            uint256_to_bytes(42),
        ),
        (
            "getGasPrice()",
            10**10,
            uint256_to_bytes(10**10),
        ),
        (
            "getGasPrice()",
            10**11,
            uint256_to_bytes(10**11),
        ),
        (
            # make sure that whatever voodoo is used to execute a call,
            # the balance is not inflated
            "getBalance()",
            10**10,
            uint256_to_bytes(0),
        ),
    ),
)
def test_get_transaction_result(
    chain, simple_contract_address, signature, gas_price, expected
):
    function_selector = function_signature_to_4byte_selector(signature)
    call_txn = new_transaction(
        chain.get_vm(),
        b"\xff" * 20,
        simple_contract_address,
        gas_price=gas_price,
        data=function_selector,
    )
    result_bytes = chain.get_transaction_result(call_txn, chain.get_canonical_head())
    assert result_bytes == expected


@pytest.mark.parametrize(
    "vm, signature, expected",
    (
        (
            FrontierVM,
            "doRevert()",
            InvalidInstruction,
        ),
        (
            FrontierVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            HomesteadVM.configure(
                support_dao_fork=False,
            ),
            "doRevert()",
            InvalidInstruction,
        ),
        (
            HomesteadVM.configure(
                support_dao_fork=False,
            ),
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            TangerineWhistleVM,
            "doRevert()",
            InvalidInstruction,
        ),
        (
            TangerineWhistleVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            SpuriousDragonVM,
            "doRevert()",
            InvalidInstruction,
        ),
        (
            SpuriousDragonVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            ByzantiumVM,
            "doRevert()",
            Revert,
        ),
        (
            ByzantiumVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            ConstantinopleVM,
            "doRevert()",
            Revert,
        ),
        (
            ConstantinopleVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            PetersburgVM,
            "doRevert()",
            Revert,
        ),
        (
            PetersburgVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            IstanbulVM,
            "doRevert()",
            Revert,
        ),
        (
            IstanbulVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            MuirGlacierVM,
            "doRevert()",
            Revert,
        ),
        (
            MuirGlacierVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            BerlinVM,
            "doRevert()",
            Revert,
        ),
        (
            BerlinVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            LondonVM,
            "doRevert()",
            Revert,
        ),
        (
            LondonVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            ArrowGlacierVM,
            "doRevert()",
            Revert,
        ),
        (
            ArrowGlacierVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
        (
            GrayGlacierVM,
            "doRevert()",
            Revert,
        ),
        (
            GrayGlacierVM,
            "useLotsOfGas()",
            OutOfGas,
        ),
    ),
)
def test_get_transaction_result_revert(
    vm, chain_from_vm, simple_contract_address, signature, expected
):
    chain = chain_from_vm(vm)
    function_selector = function_signature_to_4byte_selector(signature)
    call_txn = new_transaction(
        chain.get_vm(),
        b"\xff" * 20,
        simple_contract_address,
        data=function_selector,
    )
    with pytest.raises(expected):
        chain.get_transaction_result(call_txn, chain.get_canonical_head())
