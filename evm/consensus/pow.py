from collections import OrderedDict

from pyethash import (
    EPOCH_LENGTH,
    hashimoto_light,
    mkcache_bytes,
)

from eth_utils import (
    keccak,
)

from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.exceptions import (
    ValidationError,
)
from evm.utils.numeric import (
    big_endian_to_int,
)
from evm.validation import (
    validate_length,
    validate_lte,
)


cache_seeds = ['\x00' * 32]
cache_by_seed = OrderedDict()
cache_by_seed.max_items = 10


def get_cache(block_number):
    while len(cache_seeds) <= block_number // EPOCH_LENGTH:
        cache_seeds.append(keccak(cache_seeds[-1]))
    seed = cache_seeds[block_number // EPOCH_LENGTH]
    if seed in cache_by_seed:
        c = cache_by_seed.pop(seed)  # pop and append at end
        cache_by_seed[seed] = c
        return c
    c = mkcache_bytes(block_number)
    cache_by_seed[seed] = c
    if len(cache_by_seed) > cache_by_seed.max_items:
        cache_by_seed.popitem(last=False)  # remove last recently accessed
    return c


def check_pow(block_number, mining_hash, mix_hash, nonce, difficulty):
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
