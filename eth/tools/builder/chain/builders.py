import functools
import time
from typing import TYPE_CHECKING

from cytoolz import (
    accumulate,
    curry,
    merge,
)

from eth_utils import (
    to_dict,
    to_tuple,
    ValidationError,
)

from eth import constants
from eth.chains.base import MiningChain
from eth.db.backends.memory import MemoryDB
from eth.validation import (
    validate_vm_configuration,
)
from eth.tools.fixtures.normalization import (
    normalize_state,
)
from eth.tools.mining import POWMiningMixin
from eth.tools._utils.mappings import (
    deep_merge,
)
from eth.vm.forks import (
    FrontierVM,
    HomesteadVM,
    TangerineWhistleVM,
    SpuriousDragonVM,
    ByzantiumVM,
    ConstantinopleVM,
)

if TYPE_CHECKING:
    from typing import Dict, Union  # noqa: F401


#
# Constructors (creation of chain classes)
#
@curry
def name(class_name, chain_class):
    """
    Part of the builder pipeline for chain classes.

    Sets the class name.
    """
    return chain_class.configure(__name__=class_name)


@curry
def fork_at(vm_class, at_block, chain_class):
    """
    Part of the builder pipeline for chain classes.

    Addes a vm to the `vm_configuration` for a chain.
    """
    if chain_class.vm_configuration is not None:
        base_configuration = chain_class.vm_configuration
    else:
        base_configuration = tuple()

    vm_configuration = base_configuration + ((at_block, vm_class),)
    validate_vm_configuration(vm_configuration)
    return chain_class.configure(vm_configuration=vm_configuration)


def _is_homestead(vm_class):
    if not issubclass(vm_class, HomesteadVM):
        # It isn't a subclass of the HomesteadVM
        return False
    elif issubclass(vm_class, TangerineWhistleVM):
        # It is a subclass of on of the subsequent forks
        return False
    else:
        return True


@to_tuple
def _set_vm_dao_support_false(vm_configuration):
    for fork_block, vm_class in vm_configuration:
        if _is_homestead(vm_class):
            yield fork_block, vm_class.configure(support_dao_fork=False)
        else:
            yield fork_block, vm_class


@curry
def disable_dao_fork(chain_class):
    homstead_vms_found = any(
        _is_homestead(vm_class) for _, vm_class in chain_class.vm_configuration
    )
    if not homstead_vms_found:
        raise ValidationError("No HomesteadVM found in vm_configuration.")

    vm_configuration = _set_vm_dao_support_false(chain_class.vm_configuration)
    return chain_class.configure(vm_configuration=vm_configuration)


@to_tuple
def _set_vm_dao_fork_block_number(dao_fork_block_number, vm_configuration):
    for fork_block, vm_class in vm_configuration:
        if _is_homestead(vm_class):
            yield fork_block, vm_class.configure(
                support_dao_fork=True,
                dao_fork_block_number=dao_fork_block_number,
            )
        else:
            yield fork_block, vm_class


@curry
def dao_fork_at(dao_fork_block_number, chain_class):
    homstead_vms_found = any(
        _is_homestead(vm_class) for _, vm_class in chain_class.vm_configuration
    )
    if not homstead_vms_found:
        raise ValidationError("No HomesteadVM found in vm_configuration.")

    vm_configuration = _set_vm_dao_fork_block_number(
        dao_fork_block_number,
        chain_class.vm_configuration,
    )
    return chain_class.configure(vm_configuration=vm_configuration)


frontier_at = fork_at(FrontierVM)
homestead_at = fork_at(HomesteadVM)
tangerine_whistle_at = fork_at(TangerineWhistleVM)
spurious_dragon_at = fork_at(SpuriousDragonVM)
byzantium_at = fork_at(ByzantiumVM)
constantinople_at = fork_at(ConstantinopleVM)


GENESIS_DEFAULTS = (
    ('difficulty', 1),
    ('extra_data', constants.GENESIS_EXTRA_DATA),
    ('gas_limit', constants.GENESIS_GAS_LIMIT),
    ('gas_used', 0),
    ('bloom', 0),
    ('mix_hash', constants.ZERO_HASH32),
    ('nonce', constants.GENESIS_NONCE),
    ('block_number', constants.GENESIS_BLOCK_NUMBER),
    ('parent_hash', constants.GENESIS_PARENT_HASH),
    ('receipt_root', constants.BLANK_ROOT_HASH),
    ('uncles_hash', constants.EMPTY_UNCLE_HASH),
    ('state_root', constants.BLANK_ROOT_HASH),
    ('timestamp', int(time.time())),
    ('transaction_root', constants.BLANK_ROOT_HASH),
)


@to_dict
def _get_default_genesis_params(genesis_state):
    for key, value in GENESIS_DEFAULTS:
        if key == 'state_root' and genesis_state:
            # leave out the `state_root` if a genesis state was specified
            pass
        else:
            yield key, value


@to_tuple
def _mix_in_pow_mining(vm_configuration):
    for fork_block, vm_class in vm_configuration:
        vm_class_with_pow_mining = type(vm_class.__name__, (POWMiningMixin, vm_class), {})
        yield fork_block, vm_class_with_pow_mining


@curry
def enable_pow_mining(chain_class):
    """
    Enables proof of work mining for all VMs
    """
    if not chain_class.vm_configuration:
        raise ValidationError("Chain class has no vm_configuration")

    vm_configuration = _mix_in_pow_mining(chain_class.vm_configuration)
    return chain_class.configure(vm_configuration=vm_configuration)


class NoChainSealValidationMixin:
    @classmethod
    def validate_seal(cls, block):
        pass


class NoVMSealValidationMixin:
    @classmethod
    def validate_seal(cls, header):
        pass


@to_tuple
def _mix_in_disable_seal_validation(vm_configuration):
    for fork_block, vm_class in vm_configuration:
        vm_class_without_seal_validation = type(
            vm_class.__name__,
            (NoVMSealValidationMixin, vm_class),
            {},
        )
        yield fork_block, vm_class_without_seal_validation


@curry
def disable_pow_check(chain_class):
    if not chain_class.vm_configuration:
        raise ValidationError("Chain class has no vm_configuration")

    chain_class_without_seal_validation = type(
        chain_class.__name__,
        (NoChainSealValidationMixin, chain_class),
        {},
    )
    return chain_class_without_seal_validation.configure(  # type: ignore
        vm_configuration=_mix_in_disable_seal_validation(
            chain_class_without_seal_validation.vm_configuration  # type: ignore
        ),
    )


#
# Initializers (initialization of chain state and chain class instantiation)
#
def _fill_and_normalize_state(simple_state):
    base_state = normalize_state(simple_state)
    defaults = {address: {
        "balance": 0,
        "nonce": 0,
        "code": b"",
        "storage": {},
    } for address in base_state.keys()}
    state = deep_merge(defaults, base_state)
    return state


@curry
def genesis(chain_class, db=None, params=None, state=None):
    if state is None:
        genesis_state = {}  # type: Dict[str, Union[int, bytes, Dict[int, int]]]
    else:
        genesis_state = _fill_and_normalize_state(state)

    genesis_params_defaults = _get_default_genesis_params(genesis_state)

    if params is None:
        genesis_params = genesis_params_defaults
    else:
        genesis_params = merge(genesis_params_defaults, params)

    if db is None:
        base_db = MemoryDB()
    else:
        base_db = db

    return chain_class.from_genesis(base_db, genesis_params, genesis_state)


#
# Builders (build actual block chain)
#
@curry
def mine_block(chain, **kwargs):
    """
    Mines a single block
    """
    if not isinstance(chain, MiningChain):
        raise ValidationError('`mine_block` may only be used on MiningChain instances')
    chain.mine_block(**kwargs)
    return chain


@curry
def mine_blocks(num_blocks, chain):
    """
    Mines `num_blocks` empty blocks
    """
    if not isinstance(chain, MiningChain):
        raise ValidationError('`mine_block` may only be used on MiningChain instances')
    for _ in range(num_blocks):
        chain.mine_block()
    return chain


@curry
def import_block(block, chain):
    chain.import_block(block)
    return chain


def import_blocks(*blocks):
    @functools.wraps(import_blocks)
    def _import_blocks(chain):
        for block in blocks:
            chain.import_block(block)
        return chain
    return _import_blocks


@curry
def copy(chain):
    if not isinstance(chain, MiningChain):
        raise ValidationError("`at_block_number` may only be used with 'MiningChain")
    base_db = chain.chaindb.db
    if not isinstance(base_db, MemoryDB):
        raise ValidationError("Unsupported database type: {0}".format(type(base_db)))

    db = MemoryDB(base_db.kv_store.copy())
    chain_copy = type(chain)(db, chain.header)
    return chain_copy


def chain_split(*splits, exit_fn):
    """
    Each item in `splits` should be a sequence
    Used for forking the chain.  Should be used in conjunction with
    `at_block_number` to 'rewind' the chain back to a specific height.
    """
    if not splits:
        raise ValidationError("Cannot use `chain_split` without providing at least one split")

    @functools.wraps(chain_split)
    def _chain_split(chain):
        results = []

        for split_fns in splits:
            fork_chain = copy(chain)

            split_results = tuple(accumulate(
                lambda c, fn: fn(c),
                split_fns,
                fork_chain,
            ))
            results.append(split_results)

        return exit_fn(results)
    return _chain_split


@curry
def at_block_number(block_number, chain):
    if not isinstance(chain, MiningChain):
        raise ValidationError("`at_block_number` may only be used with 'MiningChain")
    at_block = chain.get_canonical_block_by_number(block_number)

    db = chain.chaindb.db
    chain_at_block = type(chain)(db, chain.create_header_from_parent(at_block.header))
    return chain_at_block
