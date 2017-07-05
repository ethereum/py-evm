from pyethash import mkcache_bytes, hashimoto_light

from evm.utils.hexidecimal import (
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


def check_pow(block_number, mining_hash, mix_hash, nonce, difficulty):
    validate_length(mix_hash, 32)
    validate_length(mining_hash, 32)
    validate_length(nonce, 8)
    cache = mkcache_bytes(block_number)
    mining_output = hashimoto_light(
        block_number, cache, mining_hash, big_endian_to_int(nonce))
    if mining_output[b'mix digest'] != mix_hash:
        raise ValidationError("mix hash mistmatch; {0} != {1}".format(
            encode_hex(mining_output[b'mix digest']), encode_hex(mix_hash)))
    result = big_endian_to_int(mining_output[b'result'])
    validate_lte(result, 2**256 // difficulty)
