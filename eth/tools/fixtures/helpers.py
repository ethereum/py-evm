import os
import re
from typing import (
    Any,
    Dict,
    Iterable,
    Tuple,
    Type,
    cast,
)

from eth_utils import (
    ValidationError,
    to_normalized_address,
)
from eth_utils.toolz import (
    first,
)
import rlp

from eth import (
    MainnetChain,
    constants,
)
from eth._utils.state import (
    diff_state,
)
from eth.abc import (
    BlockAPI,
    ChainAPI,
    StateAPI,
    VirtualMachineAPI,
)
from eth.chains.mainnet import (
    MainnetDAOValidatorVM,
)
from eth.db.atomic import (
    AtomicDB,
)
from eth.tools.builder.chain import (
    disable_pow_check,
)
from eth.typing import (
    AccountState,
)
from eth.vm.forks import (
    BerlinVM,
    ByzantiumVM,
    CancunVM,
    ConstantinopleVM,
    FrontierVM,
    GrayGlacierVM,
    HomesteadVM as BaseHomesteadVM,
    IstanbulVM,
    LondonVM,
    ParisVM,
    PetersburgVM,
    ShanghaiVM,
    SpuriousDragonVM,
    TangerineWhistleVM,
)


#
# State Setup
#
def setup_state(desired_state: AccountState, state: StateAPI) -> None:
    for account, account_data in desired_state.items():
        for slot, value in account_data["storage"].items():
            state.set_storage(account, slot, value)

        nonce = account_data["nonce"]
        code = account_data["code"]
        balance = account_data["balance"]

        state.set_nonce(account, nonce)
        state.set_code(account, code)
        state.set_balance(account, balance)
    state.persist()


def verify_state(expected_state: AccountState, state: StateAPI) -> None:
    diff = diff_state(expected_state, state)
    new_line = "\n"
    if diff:
        error_messages = []
        for account, field, actual_value, expected_value in diff:
            if field == "balance":
                error_messages.append(
                    f"{to_normalized_address(account)}(balance) | "
                    f"Actual: {actual_value!r} | Expected: {expected_value!r} | "
                    f"Delta: {cast(int, actual_value) - cast(int, expected_value)}"
                )
            else:
                error_messages.append(
                    f"{to_normalized_address(account)}({field}) | "
                    f"Actual: {actual_value!r} | Expected: {expected_value!r}"
                )
        raise AssertionError(
            f"State DB did not match expected state on {len(error_messages)} "
            f"values:{new_line} {f'{new_line} - '.join(error_messages)}"
        )


def _block_at_timestamp(fixture: Dict[str, Any], timestamp: int) -> int:
    transition_block = None
    for idx, block_fixture in enumerate(fixture["blocks"]):
        if "expectException" in block_fixture:
            if len(fixture["blocks"]) == idx + 1:
                transition_block = idx + 1
                break

        elif block_fixture["blockHeader"]["timestamp"] >= timestamp:
            transition_block = block_fixture["blockHeader"]["number"]
            break

    return transition_block


def transition_test_at_timestamp(
    fixture: Dict[str, Any],
    initial_vm: Type[VirtualMachineAPI],
    transition_vm: Type[VirtualMachineAPI],
    timestamp: int,
) -> Iterable[Tuple[int, Type[VirtualMachineAPI]]]:
    transition_block = _block_at_timestamp(fixture, timestamp)
    if transition_block is None:
        # This should be a transition test for "before transition". It's a bit of a
        # misnomer because it's not actually testing the transition, but it's
        # the best we can do with the data we have.
        if (
            len(fixture["blocks"]) == 1
            and fixture["blocks"][0]["blockHeader"]["timestamp"] < timestamp
        ):
            return ((0, initial_vm),)

        raise ValidationError(
            "Not a known transition test format: transition_block==None."
        )

    return (
        (0, initial_vm),
        (transition_block, transition_vm),
    )


def chain_vm_configuration(
    fixture: Dict[str, Any]
) -> Iterable[Tuple[int, Type[VirtualMachineAPI]]]:
    network = fixture["network"]

    if network == "Frontier":
        return ((0, FrontierVM),)
    elif network == "Homestead":
        HomesteadVM = BaseHomesteadVM.configure(support_dao_fork=False)
        return ((0, HomesteadVM),)
    elif network == "EIP150":
        return ((0, TangerineWhistleVM),)
    elif network == "EIP158":
        return ((0, SpuriousDragonVM),)
    elif network == "Byzantium":
        return ((0, ByzantiumVM),)
    elif network == "Constantinople":
        return ((0, ConstantinopleVM),)
    elif network == "ConstantinopleFix":
        return ((0, PetersburgVM),)
    elif network == "Istanbul":
        return ((0, IstanbulVM),)
    elif network == "Berlin":
        return ((0, BerlinVM),)
    elif network == "London":
        return ((0, LondonVM),)
    elif network == "Paris":
        return ((0, ParisVM),)
    elif network == "Shanghai":
        return ((0, ShanghaiVM),)
    elif network == "Cancun":
        return ((0, CancunVM),)

    # -- transitions -- #

    elif network == "FrontierToHomesteadAt5":
        HomesteadVM = BaseHomesteadVM.configure(support_dao_fork=False)
        return (
            (0, FrontierVM),
            (5, HomesteadVM),
        )
    elif network == "HomesteadToEIP150At5":
        HomesteadVM = BaseHomesteadVM.configure(support_dao_fork=False)
        return (
            (0, HomesteadVM),
            (5, TangerineWhistleVM),
        )
    elif network == "HomesteadToDaoAt5":
        HomesteadVM = MainnetDAOValidatorVM.configure(
            support_dao_fork=True,
            _dao_fork_block_number=5,
        )
        return ((0, HomesteadVM),)
    elif network == "EIP158ToByzantiumAt5":
        return (
            (0, SpuriousDragonVM),
            (5, ByzantiumVM),
        )
    elif network == "ByzantiumToConstantinopleFixAt5":
        return (
            (0, ByzantiumVM),
            (5, PetersburgVM),
        )
    elif network == "BerlinToLondonAt5":
        return (
            (0, BerlinVM),
            (5, LondonVM),
        )
    elif network == "ArrowGlacierToParisAtDiffC0000":
        # Transition expected at 6 for all tests written thus far
        return (
            # These tests were written before Gray Glacier was a thing. Use
            # GrayGlacierVM instead since that's when PoW -> PoS transition happens.
            # They should both pass but this is the more logical transition to test.
            (0, GrayGlacierVM),
            (6, ParisVM),
        )
    elif network == "ParisToShanghaiAtTime15k":
        return transition_test_at_timestamp(fixture, ParisVM, ShanghaiVM, 15000)
    elif network == "ShanghaiToCancunAtTime15k":
        return transition_test_at_timestamp(fixture, ShanghaiVM, CancunVM, 15000)
    else:
        raise ValueError(f"Network {network} does not match any known VM rules")


LEGACY_HEADER_FIELDS = {
    "hash",
    "parentHash",
    "uncleHash",
    "coinbase",
    "stateRoot",
    "transactionsTrie",
    "receiptTrie",
    "bloom",
    "difficulty",
    "number",
    "gasLimit",
    "gasUsed",
    "timestamp",
    "extraData",
    "mixHash",
    "nonce",
}
NON_LEGACY_HEADER_FIELDS = {
    "baseFeePerGas",
    "withdrawalsRoot",
    "blobGasUsed",
    "excessBlobGas",
    "parentBeaconBlockRoot",
}
KNOWN_HEADER_FIELDS = LEGACY_HEADER_FIELDS | NON_LEGACY_HEADER_FIELDS


def genesis_fields_from_fixture(fixture: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert all genesis fields in a fixture to a dictionary of header fields and values.
    """
    header_fields_from_fixture = fixture["genesisBlockHeader"]
    header_fields = {
        "parent_hash": header_fields_from_fixture["parentHash"],
        "uncles_hash": header_fields_from_fixture["uncleHash"],
        "coinbase": header_fields_from_fixture["coinbase"],
        "state_root": header_fields_from_fixture["stateRoot"],
        "transaction_root": header_fields_from_fixture["transactionsTrie"],
        "receipt_root": header_fields_from_fixture["receiptTrie"],
        "bloom": header_fields_from_fixture["bloom"],
        "difficulty": header_fields_from_fixture["difficulty"],
        "block_number": header_fields_from_fixture["number"],
        "gas_limit": header_fields_from_fixture["gasLimit"],
        "gas_used": header_fields_from_fixture["gasUsed"],
        "timestamp": header_fields_from_fixture["timestamp"],
        "extra_data": header_fields_from_fixture["extraData"],
        "mix_hash": header_fields_from_fixture["mixHash"],
        "nonce": header_fields_from_fixture["nonce"],
    }

    for non_legacy_field in NON_LEGACY_HEADER_FIELDS:
        if non_legacy_field in header_fields_from_fixture:
            snake_cased_field = re.sub(r"([A-Z])", r"_\1", non_legacy_field).lower()
            header_fields[snake_cased_field] = header_fields_from_fixture[
                non_legacy_field
            ]

    unused_fields = set(header_fields_from_fixture.keys()) - KNOWN_HEADER_FIELDS
    if unused_fields and len(header_fields_from_fixture) > len(KNOWN_HEADER_FIELDS):
        # Update NON_LEGACY_HEADER_FIELDS above and make sure to check
        # eth/tools/_utils/normalization.py to see if new fields need to be normalized
        # as well.
        raise ValidationError(
            "There are more fields present in the block header than there are known "
            f"fields for the header.  Unused fields: {unused_fields}."
        )

    return header_fields


def genesis_params_from_fixture(fixture: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a genesis fixture into a dict of the configurable header fields and values.

    Some fields cannot be explicitly set when creating a new header, like
    parent_hash, which is automatically set to the empty hash.
    """
    params = genesis_fields_from_fixture(fixture)

    # Confirm that (currently) non-configurable defaults are set correctly,
    #   then remove them because they cannot be configured on the header.
    defaults = (
        ("parent_hash", constants.GENESIS_PARENT_HASH),
        ("uncles_hash", constants.EMPTY_UNCLE_HASH),
        ("bloom", constants.GENESIS_BLOOM),
        ("block_number", constants.GENESIS_BLOCK_NUMBER),
        ("gas_used", constants.GENESIS_GAS_USED),
    )

    for key, default_val in defaults:
        supplied_val = params.pop(key)
        if supplied_val != default_val:
            raise ValueError(
                f"Unexpected genesis {key}: {supplied_val}, expected: {default_val}"
            )

    return params


def new_chain_from_fixture(
    fixture: Dict[str, Any], chain_cls: Type[ChainAPI] = MainnetChain
) -> ChainAPI:
    base_db = AtomicDB()

    vm_config = chain_vm_configuration(fixture)

    ChainFromFixture = chain_cls.configure(
        "ChainFromFixture",
        vm_configuration=vm_config,
    )

    if "sealEngine" in fixture and fixture["sealEngine"] == "NoProof":
        ChainFromFixture = disable_pow_check(ChainFromFixture)

    return ChainFromFixture.from_genesis(
        base_db,
        genesis_params=genesis_params_from_fixture(fixture),
        genesis_state=fixture["pre"],
    )


def apply_fixture_block_to_chain(
    block_fixture: Dict[str, Any], chain: ChainAPI, perform_validation: bool = True
) -> Tuple[BlockAPI, BlockAPI, bytes]:
    """
    :return: (provided_block, imported_block, rlp_encoded_imported_block)
    """
    # The block to import may be in a different block-class-range than the
    # chain's current one, so we use the block number specified in the
    # fixture to look up the correct block class.
    if "blockHeader" in block_fixture:
        block_number = block_fixture["blockHeader"]["number"]
        block_class = chain.get_vm_class_for_block_number(
            block_number
        ).get_block_class()
    else:
        block_class = chain.get_vm().get_block_class()

    block = rlp.decode(block_fixture["rlp"], sedes=block_class)

    import_result = chain.import_block(block, perform_validation=perform_validation)
    imported_block = import_result.imported_block

    rlp_encoded_imported_block = rlp.encode(imported_block, sedes=block_class)

    return (block, imported_block, rlp_encoded_imported_block)


def should_run_slow_tests() -> bool:
    if os.environ.get("TRAVIS_EVENT_TYPE") == "cron":
        return True
    return False


def get_test_name(filler: Dict[str, Any]) -> str:
    assert len(filler) == 1
    return first(filler)
