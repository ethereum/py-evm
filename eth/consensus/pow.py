from collections import OrderedDict
from typing import (  # noqa: F401
    List,
    Tuple
)

from pyethash import (
    EPOCH_LENGTH,
    hashimoto_light,
    mkcache_bytes,
)

from eth_typing import (
    Hash32
)
from eth_utils import (
    ValidationError,
)

from eth_hash.auto import keccak

from eth.utils.hexadecimal import (
    encode_hex,
)
from eth.utils.numeric import (
    big_endian_to_int,
)
from eth.validation import (
    validate_length,
    validate_lte,
)


# Type annotation here is to ensure we don't accidentally use strings instead of bytes.
cache_seeds = [b'\x00' * 32]  # type: List[bytes]
cache_by_seed = OrderedDict()  # type: OrderedDict[bytes, bytearray]
CACHE_MAX_ITEMS = 10


def get_cache(block_number: int) -> bytes:
    while len(cache_seeds) <= block_number // EPOCH_LENGTH:
        cache_seeds.append(keccak(cache_seeds[-1]))
    seed = cache_seeds[block_number // EPOCH_LENGTH]
    if seed in cache_by_seed:
        c = cache_by_seed.pop(seed)  # pop and append at end
        cache_by_seed[seed] = c
        return c
    c = mkcache_bytes(block_number)
    cache_by_seed[seed] = c
    if len(cache_by_seed) > CACHE_MAX_ITEMS:
        cache_by_seed.popitem(last=False)  # remove last recently accessed
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
        raise ValidationError("mix hash mismatch; {0} != {1}".format(
            encode_hex(mining_output[b'mix digest']), encode_hex(mix_hash)))
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
