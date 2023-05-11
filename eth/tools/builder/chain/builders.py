import functools
import time
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Tuple,
    Type,
    Union,
    cast,
)

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
)
from eth_utils import (
    ValidationError,
    to_dict,
    to_tuple,
)
from eth_utils.toolz import (
    curry,
    merge,
    pipe,
)

from eth import (
    constants,
)
from eth.abc import (
    AtomicDatabaseAPI,
    BlockAPI,
    ChainAPI,
    MiningChainAPI,
    VirtualMachineAPI,
)
from eth.consensus.applier import (
    ConsensusApplier,
)
from eth.consensus.noproof import (
    NoProofConsensus,
)
from eth.db.atomic import (
    AtomicDB,
)
from eth.db.backends.memory import (
    MemoryDB,
)
from eth.rlp.headers import (
    HeaderParams,
)
from eth.tools._utils.mappings import (
    deep_merge,
)
from eth.tools._utils.normalization import (
    normalize_state,
)
from eth.tools.mining import (
    POWMiningMixin,
)
from eth.typing import (
    AccountState,
    GeneralState,
    VMConfiguration,
    VMFork,
)
from eth.validation import (
    validate_vm_configuration,
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
    ParisVM,
    PetersburgVM,
    ShanghaiVM,
    SpuriousDragonVM,
    TangerineWhistleVM,
)


def build(obj: Any, *applicators: Callable[..., Any]) -> Any:
    """
    Run the provided object through the series of applicator functions.

    If ``obj`` is an instances of :class:`~eth.chains.base.BaseChain` the
    applicators will be run on a copy of the chain and thus will not mutate the
    provided chain instance.
    """
    if isinstance(obj, ChainAPI):
        return pipe(obj, copy(), *applicators)
    else:
        return pipe(obj, *applicators)


#
# Constructors (creation of chain classes)
#
@curry
def name(class_name: str, chain_class: Type[ChainAPI]) -> Type[ChainAPI]:
    """
    Assign the given name to the chain class.
    """
    return chain_class.configure(__name__=class_name)


@curry
def chain_id(chain_id: int, chain_class: Type[ChainAPI]) -> Type[ChainAPI]:
    """
    Set the ``chain_id`` for the chain class.
    """
    return chain_class.configure(chain_id=chain_id)


@curry
def fork_at(
    vm_class: Type[VirtualMachineAPI],
    at_block: Union[int, BlockNumber],
    chain_class: Type[ChainAPI],
) -> Type[ChainAPI]:
    """
    Adds the ``vm_class`` to the chain's ``vm_configuration``.

    .. code-block:: python

        from eth.chains.base import MiningChain
        from eth.tools.builder.chain import build, fork_at

        FrontierOnlyChain = build(MiningChain, fork_at(FrontierVM, 0))

        # these two classes are functionally equivalent.
        class FrontierOnlyChain(MiningChain):
            vm_configuration = (
                (0, FrontierVM),
            )

    .. note:: This function is curriable.

    The following pre-curried versions of this function are available as well,
    one for each mainnet fork.

    * :func:`~eth.tools.builder.chain.frontier_at`
    * :func:`~eth.tools.builder.chain.homestead_at`
    * :func:`~eth.tools.builder.chain.tangerine_whistle_at`
    * :func:`~eth.tools.builder.chain.spurious_dragon_at`
    * :func:`~eth.tools.builder.chain.byzantium_at`
    * :func:`~eth.tools.builder.chain.constantinople_at`
    * :func:`~eth.tools.builder.chain.petersburg_at`
    * :func:`~eth.tools.builder.chain.istanbul_at`
    * :func:`~eth.tools.builder.chain.muir_glacier_at`
    * :func:`~eth.tools.builder.chain.berlin_at`
    * :func:`~eth.tools.builder.chain.london_at`
    * :func:`~eth.tools.builder.chain.arrow_glacier_at`
    * :func:`~eth.tools.builder.chain.gray_glacier_at`
    * :func:`~eth.tools.builder.chain.latest_mainnet_at` - whatever latest mainnet VM is
    """
    if chain_class.vm_configuration is not None:
        base_configuration = chain_class.vm_configuration
    else:
        base_configuration = ()

    vm_configuration = base_configuration + ((BlockNumber(at_block), vm_class),)
    validate_vm_configuration(vm_configuration)
    return chain_class.configure(vm_configuration=vm_configuration)


def _is_homestead(vm_class: Type[VirtualMachineAPI]) -> bool:
    if not issubclass(vm_class, HomesteadVM):
        # It isn't a subclass of the HomesteadVM
        return False
    elif issubclass(vm_class, TangerineWhistleVM):
        # It is a subclass of one of the subsequent forks
        return False
    else:
        return True


@to_tuple
def _set_vm_dao_support_false(vm_configuration: VMConfiguration) -> Iterable[VMFork]:
    for fork_block, vm_class in vm_configuration:
        if _is_homestead(vm_class):
            yield fork_block, vm_class.configure(support_dao_fork=False)
        else:
            yield fork_block, vm_class


@curry
def disable_dao_fork(chain_class: Type[ChainAPI]) -> Type[ChainAPI]:
    """
    Set the ``support_dao_fork`` flag to ``False`` on the
    :class:`~eth.vm.forks.homestead.HomesteadVM`.  Requires that presence of
    the :class:`~eth.vm.forks.homestead.HomesteadVM`  in the
    ``vm_configuration``
    """
    homstead_vms_found = any(
        _is_homestead(vm_class) for _, vm_class in chain_class.vm_configuration
    )
    if not homstead_vms_found:
        raise ValidationError("No HomesteadVM found in vm_configuration.")

    vm_configuration = _set_vm_dao_support_false(chain_class.vm_configuration)
    return chain_class.configure(vm_configuration=vm_configuration)


@to_tuple
def _set_vm_dao_fork_block_number(
    dao_fork_block_number: BlockNumber, vm_configuration: VMConfiguration
) -> Iterable[VMFork]:
    for fork_block, vm_class in vm_configuration:
        if _is_homestead(vm_class):
            yield fork_block, vm_class.configure(
                support_dao_fork=True,
                _dao_fork_block_number=dao_fork_block_number,
            )
        else:
            yield fork_block, vm_class


@curry
def dao_fork_at(
    dao_fork_block_number: BlockNumber, chain_class: Type[ChainAPI]
) -> Type[ChainAPI]:
    """
    Set the block number on which the DAO fork will happen.  Requires that a
    version of the :class:`~eth.vm.forks.homestead.HomesteadVM` is present in
    the chain's ``vm_configuration``

    """
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
petersburg_at = fork_at(PetersburgVM)
istanbul_at = fork_at(IstanbulVM)
muir_glacier_at = fork_at(MuirGlacierVM)
berlin_at = fork_at(BerlinVM)
london_at = fork_at(LondonVM)
arrow_glacier_at = fork_at(ArrowGlacierVM)
gray_glacier_at = fork_at(GrayGlacierVM)
paris_at = fork_at(ParisVM)
shanghai_at = fork_at(ShanghaiVM)

latest_mainnet_at = shanghai_at

GENESIS_DEFAULTS = cast(
    Tuple[Tuple[str, Union[BlockNumber, int, None, bytes, Address, Hash32]], ...],
    # values that will automatically be default are commented out
    (
        ("difficulty", 1),
        ("extra_data", constants.GENESIS_EXTRA_DATA),
        ("gas_limit", constants.GENESIS_GAS_LIMIT),
        # ('gas_used', 0),
        # ('bloom', 0),
        ("mix_hash", constants.ZERO_HASH32),
        ("nonce", constants.GENESIS_NONCE),
        # ('block_number', constants.GENESIS_BLOCK_NUMBER),
        # ('parent_hash', constants.GENESIS_PARENT_HASH),
        ("receipt_root", constants.BLANK_ROOT_HASH),
        # ('uncles_hash', constants.EMPTY_UNCLE_HASH),
        ("state_root", constants.BLANK_ROOT_HASH),
        ("transaction_root", constants.BLANK_ROOT_HASH),
    ),
)


@to_dict
def _get_default_genesis_params(
    genesis_state: AccountState,
) -> Iterable[Tuple[str, Union[BlockNumber, int, None, bytes, Address, Hash32]]]:
    for key, value in GENESIS_DEFAULTS:
        if key == "state_root" and genesis_state:
            # leave out the `state_root` if a genesis state was specified
            pass
        else:
            yield key, value
    yield "timestamp", int(time.time())  # populate the timestamp value at runtime


@to_tuple
def _mix_in_pow_mining(vm_configuration: VMConfiguration) -> Iterable[VMFork]:
    for fork_block, vm_class in vm_configuration:
        vm_class_with_pow_mining = type(
            vm_class.__name__, (POWMiningMixin, vm_class), {}
        )
        yield fork_block, vm_class_with_pow_mining


@curry
def enable_pow_mining(chain_class: Type[ChainAPI]) -> Type[ChainAPI]:
    """
    Inject on demand generation of the proof of work mining seal on newly
    mined blocks into each of the chain's vms.
    """
    if not chain_class.vm_configuration:
        raise ValidationError("Chain class has no vm_configuration")

    vm_configuration = _mix_in_pow_mining(chain_class.vm_configuration)
    return chain_class.configure(vm_configuration=vm_configuration)


@curry
def disable_pow_check(chain_class: Type[ChainAPI]) -> Type[ChainAPI]:
    """
    Disable the proof of work validation check for each of the chain's vms.
    This allows for block mining without generation of the proof of work seal.

    .. note::

        blocks mined this way will not be importable on any chain that does not
        have proof of work disabled.
    """
    original_vms = chain_class.vm_configuration
    no_pow_vms = ConsensusApplier(NoProofConsensus).amend_vm_configuration(original_vms)

    return chain_class.configure(vm_configuration=no_pow_vms)


#
# Initializers (initialization of chain state and chain class instantiation)
#
def _fill_and_normalize_state(simple_state: GeneralState) -> AccountState:
    base_state = normalize_state(simple_state)
    defaults = {
        address: {
            "balance": 0,
            "nonce": 0,
            "code": b"",
            "storage": {},
        }
        for address in base_state.keys()
    }
    state = deep_merge(defaults, base_state)
    return state


@curry
def genesis(
    chain_class: ChainAPI,
    db: AtomicDatabaseAPI = None,
    params: Dict[str, HeaderParams] = None,
    state: GeneralState = None,
) -> ChainAPI:
    """
    Initialize the given chain class with the given genesis header parameters
    and chain state.
    """
    if state is None:
        genesis_state: AccountState = {}
    else:
        genesis_state = _fill_and_normalize_state(state)

    genesis_params_defaults = _get_default_genesis_params(genesis_state)

    if params is None:
        genesis_params = genesis_params_defaults
    else:
        genesis_params = merge(genesis_params_defaults, params)

    if db is None:
        base_db: AtomicDatabaseAPI = AtomicDB()
    else:
        base_db = db

    return chain_class.from_genesis(base_db, genesis_params, genesis_state)


#
# Builders (build actual blockchain)
#
@curry
def mine_block(chain: MiningChainAPI, **kwargs: Any) -> MiningChainAPI:
    """
    Mine a new block on the chain.  Header parameters for the new block can be
    overridden using keyword arguments.

    """

    if not isinstance(chain, MiningChainAPI):
        raise ValidationError("`mine_block` may only be used on MiningChain instances")

    transactions = kwargs.pop("transactions", ())

    chain.mine_all(transactions, **kwargs)
    return chain


@curry
def mine_blocks(num_blocks: int, chain: MiningChainAPI) -> MiningChainAPI:
    """
    Variadic argument version of :func:`~eth.tools.builder.chain.mine_block`
    """
    if not isinstance(chain, MiningChainAPI):
        raise ValidationError("`mine_block` may only be used on MiningChain instances")
    for _ in range(num_blocks):
        chain.mine_block()
    return chain


@curry
def import_block(block: BlockAPI, chain: ChainAPI) -> ChainAPI:
    """
    Import the provided ``block`` into the chain.
    """
    chain.import_block(block)
    return chain


def import_blocks(*blocks: BlockAPI) -> Callable[[ChainAPI], ChainAPI]:
    """
    Variadic argument version of :func:`~eth.tools.builder.chain.import_block`
    """

    @functools.wraps(import_blocks)
    def _import_blocks(chain: ChainAPI) -> ChainAPI:
        for block in blocks:
            chain.import_block(block)
        return chain

    return _import_blocks


@curry
def copy(chain: MiningChainAPI) -> MiningChainAPI:
    """
    Make a copy of the chain at the given state.  Actions performed on the
    resulting chain will not affect the original chain.
    """
    if not isinstance(chain, MiningChainAPI):
        raise ValidationError("`at_block_number` may only be used with 'MiningChain")
    base_db = chain.chaindb.db
    if not isinstance(base_db, AtomicDB):
        raise ValidationError(f"Unsupported database type: {type(base_db)}")

    if isinstance(base_db.wrapped_db, MemoryDB):
        db = AtomicDB(MemoryDB(base_db.wrapped_db.kv_store.copy()))
    else:
        raise ValidationError(
            f"Unsupported wrapped database: {type(base_db.wrapped_db)}"
        )

    chain_copy = type(chain)(db, chain.header)
    return chain_copy


def chain_split(
    *splits: Iterable[Callable[..., Any]]
) -> Callable[[ChainAPI], Iterable[ChainAPI]]:
    """
    Construct and execute multiple concurrent forks of the chain.

    Any number of forks may be executed.  For each fork, provide an iterable of
    commands.

    Returns the resulting chain objects for each fork.


    .. code-block:: python

        chain_a, chain_b = build(
            mining_chain,
            chain_split(
                (mine_block(extra_data=b'chain-a'), mine_block()),
                (mine_block(extra_data=b'chain-b'), mine_block(), mine_block()),
            ),
        )
    """
    if not splits:
        raise ValidationError(
            "Cannot use `chain_split` without providing at least one split"
        )

    @functools.wraps(chain_split)
    @to_tuple
    def _chain_split(chain: ChainAPI) -> Iterable[ChainAPI]:
        for split_fns in splits:
            result = build(
                chain,
                *split_fns,
            )
            yield result

    return _chain_split


@curry
def at_block_number(
    block_number: Union[int, BlockNumber], chain: MiningChainAPI
) -> MiningChainAPI:
    """
    Rewind the chain back to the given block number.  Calls to things like
    ``get_canonical_head`` will still return the canonical head of the chain,
    however, you can use ``mine_block`` to mine fork chains.
    """
    if not isinstance(chain, MiningChainAPI):
        raise ValidationError("`at_block_number` may only be used with 'MiningChain")
    at_block = chain.get_canonical_block_by_number(BlockNumber(block_number))

    db = chain.chaindb.db
    chain_at_block = type(chain)(db, chain.create_header_from_parent(at_block.header))
    return chain_at_block
