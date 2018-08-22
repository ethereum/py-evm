from .builders import (  # noqa: F401
    dao_fork_at,
    disable_dao_fork,
    enable_pow_mining,
    disable_pow_check,
    fork_at,
    name,
    genesis,
    mine_block,
    mine_blocks,
    chain_split,
    at_block_number,
    copy,
    import_block,
    import_blocks,
)
from .builders import (  # noqa: F401
    byzantium_at,
    frontier_at,
    homestead_at,
    spurious_dragon_at,
    tangerine_whistle_at,
    constantinople_at,
)


mainnet_fork_at_fns = (
    byzantium_at,
    frontier_at,
    homestead_at,
    spurious_dragon_at,
    tangerine_whistle_at,
    constantinople_at,
)


class API:
    #
    # Chain Class Construction
    #

    # Configure chain vm_configuration
    fork_at = staticmethod(fork_at)

    # Mainnet Forks
    frontier_at = staticmethod(frontier_at)
    homestead_at = staticmethod(homestead_at)
    tangerine_whistle_at = staticmethod(tangerine_whistle_at)
    spurious_dragon_at = staticmethod(spurious_dragon_at)
    byzantium_at = staticmethod(byzantium_at)
    constantinople_at = staticmethod(constantinople_at)

    # iterable of the fork specific functions
    mainnet_fork_at_fns = staticmethod(mainnet_fork_at_fns)

    # DAO Fork specific
    dao_fork_at = staticmethod(dao_fork_at)
    disable_dao_fork = staticmethod(disable_dao_fork)

    # Chain Mining config
    enable_pow_mining = staticmethod(enable_pow_mining)
    disable_pow_check = staticmethod(disable_pow_check)

    #
    # Chain Instance Initialization
    #
    name = staticmethod(name)
    genesis = staticmethod(genesis)

    #
    # Chain Building
    #
    copy = staticmethod(copy)

    import_block = staticmethod(import_block)
    import_blocks = staticmethod(import_blocks)

    mine_block = staticmethod(mine_block)
    mine_blocks = staticmethod(mine_blocks)

    chain_split = staticmethod(chain_split)
    at_block_number = staticmethod(at_block_number)


api = API()