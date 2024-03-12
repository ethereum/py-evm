"""
This file was heavily inspired by and borrowed from the ethereum.org page on Ethash,
as well as the ``ethereum/execution-specs`` repository implementation of Ethash.
"""
from typing import (
    Callable,
    Dict,
    Sequence,
    Tuple,
    Union,
)

from Crypto.Hash import (
    keccak as pc_keccak,
)
from eth_typing import (
    Hash32,
)

WORD_BYTES = 4  # bytes in word
DATASET_BYTES_INIT = 2**30  # bytes in dataset at genesis
DATASET_BYTES_GROWTH = 2**23  # dataset growth per epoch
CACHE_BYTES_INIT = 2**24  # bytes in cache at genesis
CACHE_BYTES_GROWTH = 2**17  # cache growth per epoch
CACHE_MULTIPLIER = 1024  # Size of the DAG relative to the cache
EPOCH_LENGTH = 30000  # blocks per epoch
MIX_BYTES = 128  # width of mix
HASH_BYTES = 64  # hash length in bytes
DATASET_PARENTS = 256  # number of parents of each dataset element
CACHE_ROUNDS = 3  # number of rounds in cache production
ACCESSES = 64  # number of accesses in hashimoto loop

FNV_PRIME = 0x01000193


def fnv(v1: int, v2: int) -> int:
    return ((v1 * FNV_PRIME) ^ v2) % 2**32


def encode_int(num: int) -> str:
    return hex(num)[2::-1]  # strip off '0x', and reverse


def zpad(foo: str, length: int) -> str:
    return foo + "\x00" * max(0, length - len(foo))


def keccak_256(seed: bytes) -> bytes:
    hasher = pc_keccak.new(data=seed, digest_bits=256)
    return hasher.digest()


def keccak_512(seed: bytes) -> bytes:
    hasher = pc_keccak.new(data=seed, digest_bits=512)
    return hasher.digest()


def get_cache_size(block_number: int) -> int:
    sz = CACHE_BYTES_INIT + CACHE_BYTES_GROWTH * (block_number // EPOCH_LENGTH)
    sz -= HASH_BYTES
    while not isprime(sz // HASH_BYTES):
        sz -= 2 * HASH_BYTES
    return sz


def get_dataset_full_size(block_number: int) -> int:
    sz = DATASET_BYTES_INIT + DATASET_BYTES_GROWTH * (block_number // EPOCH_LENGTH)
    sz -= MIX_BYTES
    while not isprime(sz / MIX_BYTES):
        sz -= 2 * MIX_BYTES
    return sz


def isprime(x: Union[int, float]) -> bool:
    for i in range(2, int(x**0.5)):
        if x % i == 0:
            return False
    return True


def serialize_hash(h: bytes) -> bytes:
    foo = "".join([zpad(encode_int(x), 4) for x in h])
    return foo.encode()


def generate_seed_hash(block_number: int) -> bytes:
    epoch = block_number // EPOCH_LENGTH
    seed = b"\x00" * 32
    while epoch != 0:
        seed = serialize_hash(keccak_256(seed))
        epoch -= 1
    return seed


def xor(first_item: bytes, second_item: int) -> bytes:
    return bytes([a ^ b for a, b in zip(first_item, bytes(second_item))])


def mkcache(block_number: int) -> Tuple[Tuple[int, ...], ...]:
    cache_size = get_cache_size(block_number)
    cache_size_words = cache_size // HASH_BYTES

    seed = generate_seed_hash(block_number)

    # Sequentially produce the initial dataset
    cache = [keccak_512(seed)]
    previous_cache_item = cache[0]
    for _ in range(1, cache_size_words):
        cache_item = keccak_512(previous_cache_item)
        cache.append(cache_item)
        previous_cache_item = cache_item

    # Use a low-round version of `RandMemoHash` algorithm
    for _ in range(CACHE_ROUNDS):
        for i in range(cache_size_words):
            first_cache_item = cache[i - 1 + int(cache_size_words) % cache_size_words]
            foo = bytes_to_int(cache[i][0:4])
            second_cache_item = foo % cache_size_words
            result = xor(first_cache_item, second_cache_item)
            cache[i] = keccak_512(result)

    return tuple(le_bytes_to_uint32_sequence(cache_item) for cache_item in cache)


def int_to_le_bytes(val: int, num_bytes: int = None) -> bytes:
    if num_bytes is None:
        bit_length = int(val).bit_length()
        num_bytes = (bit_length + 7) // 8
    return val.to_bytes(num_bytes, "little")


def bytes_to_int(val: bytes) -> int:
    return int.from_bytes(val, "little")


def le_bytes_to_uint32_sequence(data: bytes) -> Tuple[int, ...]:
    sequence = []
    for i in range(0, len(data), 4):
        sequence.append(bytes_to_int(data[i : i + 4]))

    return tuple(sequence)


def le_uint32_sequence_to_bytes(sequence: Sequence[int]) -> bytes:
    result_bytes = b""
    for item in sequence:
        result_bytes += int_to_le_bytes(item, 4)

    return result_bytes


def from_le_bytes(data: bytes) -> int:
    return bytes_to_int(data)


def le_uint32_sequence_to_uint(sequence: Sequence[int]) -> int:
    sequence_as_bytes = le_uint32_sequence_to_bytes(sequence)
    return from_le_bytes(sequence_as_bytes)


def fnv_hash(mix_integers: Tuple[int, ...], data: Tuple[int, ...]) -> Tuple[int, ...]:
    return tuple(fnv(mix_integers[i], data[i]) for i in range(len(mix_integers)))


def calc_dataset_item(cache: Tuple[Tuple[int, ...], ...], i: int) -> Tuple[int, ...]:
    n = len(cache)
    r = HASH_BYTES // WORD_BYTES  # 16

    mix = keccak_512(
        int_to_le_bytes((le_uint32_sequence_to_uint(cache[i % n]) ^ i), HASH_BYTES)
    )
    mix_integers = le_bytes_to_uint32_sequence(mix)

    # fnv it with a lot of random cache nodes based on i
    for j in range(DATASET_PARENTS):
        cache_index = fnv(i ^ j, mix_integers[j % r])
        mix_integers = fnv_hash(mix_integers, cache[cache_index % n])

    mix = le_uint32_sequence_to_bytes(mix_integers)
    return le_bytes_to_uint32_sequence(keccak_512(mix))


def _hashimoto(
    header_hash: bytes,
    nonce: bytes,
    dataset_size: int,
    fetch_dataset_item: Callable[[int], Tuple[int, ...]],
) -> Dict[str, bytes]:
    mix_hashes = MIX_BYTES // HASH_BYTES

    nonce_le = bytes(reversed(nonce))
    seed_hash = keccak_512(header_hash + nonce_le)
    seed_head = from_le_bytes(seed_hash[:4])

    rows = dataset_size // 128
    mix = le_bytes_to_uint32_sequence(seed_hash) * mix_hashes

    for i in range(ACCESSES):
        new_data: Tuple[int, ...] = ()
        parent = fnv(i ^ seed_head, mix[i % len(mix)]) % rows
        for j in range(MIX_BYTES // HASH_BYTES):
            new_data += fetch_dataset_item(2 * parent + j)

        mix = fnv_hash(mix, new_data)

    compressed_mix = []
    for i in range(0, len(mix), 4):
        compressed_mix.append(fnv(fnv(fnv(mix[i], mix[i + 1]), mix[i + 2]), mix[i + 3]))

    mix_digest = le_uint32_sequence_to_bytes(compressed_mix)
    result = keccak_256(seed_hash + mix_digest)

    return {"mix_digest": mix_digest, "result": result}


def hashimoto_light(
    full_size: int, cache: Tuple[Tuple[int, ...], ...], header: Hash32, nonce: bytes
) -> Dict[str, bytes]:
    return _hashimoto(
        header,
        nonce,
        full_size,
        lambda x: calc_dataset_item(cache, x),
    )


def hashimoto(
    full_size: int, dataset: Tuple[Tuple[int, ...], ...], header: Hash32, nonce: bytes
) -> Dict[str, bytes]:
    return _hashimoto(
        header,
        nonce,
        full_size,
        lambda x: dataset[x],
    )
