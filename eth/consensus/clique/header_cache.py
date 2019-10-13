from typing import Dict

from eth_typing import Hash32
from eth_utils import get_extended_debug_logger

from eth.abc import ChainDatabaseAPI
from eth.rlp.headers import BlockHeader


class HeaderCache:
    """
    The ``HeaderCache`` is responsible for holding on to all headers during validation until
    they are persisted in the database. This is necessary because validation in Clique depends
    on looking up past headers which may not be persisted at the time when they are needed.
    """

    logger = get_extended_debug_logger('eth.consensus.clique.header_cache.HeaderCache')

    def __init__(self, chaindb: ChainDatabaseAPI) -> None:
        self._chaindb = chaindb
        self._cache: Dict[Hash32, BlockHeader] = {}
        self._gc_threshold = 1000

    def __getitem__(self, key: Hash32) -> BlockHeader:
        return self._cache[key]

    def __setitem__(self, key: Hash32, value: BlockHeader) -> None:
        self._cache[key] = value

    def __contains__(self, key: bytes) -> bool:
        return key in self._cache

    def __delitem__(self, key: Hash32) -> None:
        del self._cache[key]

    def __len__(self) -> int:
        return len(self._cache)

    def evict(self) -> None:
        """
        Evict all headers from the cache that have a block number lower than the oldest
        block number that is considered needed.
        """
        head = self._chaindb.get_canonical_head()
        oldest_needed_header = head.block_number - self._gc_threshold

        for header in list(self._cache.values()):
            if header.block_number < oldest_needed_header:
                self._cache.pop(header.hash)

        self.logger.debug2("Finished cache cleanup. Cache length: %s", len(self))
