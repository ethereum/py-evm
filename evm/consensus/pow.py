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


def check_pow(block_number, mining_hash, mix_hash, nonce, difficulty):
    if len(mix_hash) != 32:
        raise ValidationError(
            "mix_hash should have length 32, got {0}: {1}".format(
                len(mix_hash), mix_hash))
    elif len(mining_hash) != 32:
        raise ValidationError(
            "mining_hash should have length 32, got {0}: {1}".format(
                len(mining_hash), mining_hash))
    elif len(nonce) != 8:
        raise ValidationError(
            "nonce should have length 8, got {0}: {1}".format(
                len(nonce), nonce))

    cache = mkcache_bytes(block_number)
    mining_output = hashimoto_light(
        block_number, cache, mining_hash, big_endian_to_int(nonce))
    if mining_output[b'mix digest'] != mix_hash:
        raise ValidationError("mix hash mistmatch; {0} != {1}".format(
            encode_hex(mining_output[b'mix digest']), encode_hex(mix_hash)))
    result = big_endian_to_int(mining_output[b'result'])
    if not (result <= 2**256 // difficulty):
        raise ValidationError("Wrong difficulty")
