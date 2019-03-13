from collections import OrderedDict
from typing import (  # noqa: F401
    Dict,
    List,
    Tuple
)

from eth_typing import (
    Hash32
)

from eth_utils import (
    big_endian_to_int,
    ValidationError,
    encode_hex,
)

from eth_hash.auto import keccak

from pyethash import (
    EPOCH_LENGTH,
    hashimoto_light,
    mkcache_bytes,
)


from eth.validation import (
    validate_length,
    validate_lte,
)


# Type annotation here is to ensure we don't accidentally use strings instead of bytes.
cache_by_epoch = OrderedDict()  # type: OrderedDict[int, bytearray]
CACHE_MAX_ITEMS = 10


def get_cache(block_number: int) -> bytes:
    epoch_index = block_number // EPOCH_LENGTH

    # doing explicit caching, because functools.lru_cache is 70% slower in the tests

    # Get the cache if already generated, marking it as recently used
    if epoch_index in cache_by_epoch:
        c = cache_by_epoch.pop(epoch_index)  # pop and append at end
        cache_by_epoch[epoch_index] = c
        return c

    # Generate the cache if it was not already in memory
    # Simulate requesting mkcache by block number: multiply index by epoch length
    c = mkcache_bytes(epoch_index * EPOCH_LENGTH)
    cache_by_epoch[epoch_index] = c

    # Limit memory usage for cache
    if len(cache_by_epoch) > CACHE_MAX_ITEMS:
        cache_by_epoch.popitem(last=False)  # remove last recently accessed

    return c


def check_pow(block_number: int,
              mining_hash: Hash32,
              mix_hash: Hash32,
              nonce: bytes,
              difficulty: int) -> None:
    validate_length(mix_hash, 32, title="Mix Hash")
    validate_length(mining_hash, 32, title="Mining Hash")
    validate_length(nonce, 8, title="POW Nonce")
    cache = get_cache(block_number)
    mining_output = hashimoto_light(
        block_number, cache, mining_hash, big_endian_to_int(nonce))
    if mining_output[b'mix digest'] != mix_hash:
        raise ValidationError(
            "mix hash mismatch; expected: {} != actual: {}. "
            "Mix hash calculated from block #{}, mine hash {}, nonce {}, difficulty {}, "
            "cache hash {}".format(
                encode_hex(mining_output[b'mix digest']),
                encode_hex(mix_hash),
                block_number,
                encode_hex(mining_hash),
                encode_hex(nonce),
                difficulty,
                encode_hex(keccak(cache)),
            )
        )
    result = big_endian_to_int(mining_output[b'result'])
    validate_lte(result, 2**256 // difficulty, title="POW Difficulty")


MAX_TEST_MINE_ATTEMPTS = 1000


def mine_pow_nonce(block_number: int, mining_hash: Hash32, difficulty: int) -> Tuple[bytes, bytes]:
    cache = get_cache(block_number)
    for nonce in range(MAX_TEST_MINE_ATTEMPTS):
        mining_output = hashimoto_light(block_number, cache, mining_hash, nonce)
        result = big_endian_to_int(mining_output[b'result'])
        result_cap = 2**256 // difficulty
        if result <= result_cap:
            return nonce.to_bytes(8, 'big'), mining_output[b'mix digest']

    raise Exception("Too many attempts at POW mining, giving up")
