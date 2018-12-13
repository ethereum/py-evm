from typing import (  # noqa: F401
    Dict,
    Iterable,
    Tuple,
    Union,
)


from py_ecc.optimized_bn128 import (  # NOQA
    G1,
    G2,
    Z1,
    Z2,
    neg,
    add,
    multiply,
    FQ,
    FQ2,
    FQ12,
    FQP,
    pairing,
    normalize,
    field_modulus,
    b,
    b2,
    is_on_curve,
    curve_order,
    final_exponentiate
)
from eth.utils.blake import blake
from eth.utils.bn128 import (
    FQP_point_to_FQ2_point,
)


CACHE = {}  # type: Dict[bytes, Tuple[FQ2, FQ2, FQ2]]
# 16th root of unity
HEX_ROOT = FQ2([21573744529824266246521972077326577680729363968861965890554801909984373949499,
                16854739155576650954933913186877292401521110422362946064090026408937773542853])


assert HEX_ROOT ** 8 != FQ2([1, 0])
assert HEX_ROOT ** 16 == FQ2([1, 0])


def compress_G1(pt: Tuple[FQ, FQ, FQ]) -> int:
    x, y = normalize(pt)
    return x.n + 2**255 * (y.n % 2)


def decompress_G1(p: int) -> Tuple[FQ, FQ, FQ]:
    if p == 0:
        return (FQ(1), FQ(1), FQ(0))
    x = p % 2**255
    y_mod_2 = p // 2**255
    y = pow((x**3 + b.n) % field_modulus, (field_modulus + 1) // 4, field_modulus)
    assert pow(y, 2, field_modulus) == (x**3 + b.n) % field_modulus
    if y % 2 != y_mod_2:
        y = field_modulus - y
    return (FQ(x), FQ(y), FQ(1))


def sqrt_fq2(x: FQP) -> FQ2:
    y = x ** ((field_modulus ** 2 + 15) // 32)
    while y**2 != x:
        y *= HEX_ROOT
    return FQ2(y.coeffs)


def hash_to_G2(m: bytes) -> Tuple[FQ2, FQ2, FQ2]:
    """
    WARNING: this function has not been standardized yet.
    """
    if m in CACHE:
        return CACHE[m]
    k2 = m
    while 1:
        k1 = blake(k2)
        k2 = blake(k1)
        x1 = int.from_bytes(k1, 'big') % field_modulus
        x2 = int.from_bytes(k2, 'big') % field_modulus
        x = FQ2([x1, x2])
        xcb = x**3 + b2
        if xcb ** ((field_modulus ** 2 - 1) // 2) == FQ2([1, 0]):
            break
    y = sqrt_fq2(xcb)

    o = FQP_point_to_FQ2_point(multiply((x, y, FQ2([1, 0])), 2 * field_modulus - curve_order))
    CACHE[m] = o
    return o


def compress_G2(pt: Tuple[FQP, FQP, FQP]) -> Tuple[int, int]:
    assert is_on_curve(pt, b2)
    x, y = normalize(pt)
    return (
        int(x.coeffs[0] + 2**255 * (y.coeffs[0] % 2)),
        int(x.coeffs[1])
    )


def decompress_G2(p: bytes) -> Tuple[FQP, FQP, FQP]:
    x1 = p[0] % 2**255
    y1_mod_2 = p[0] // 2**255
    x2 = p[1]
    x = FQ2([x1, x2])
    if x == FQ2([0, 0]):
        return FQ2([1, 0]), FQ2([1, 0]), FQ2([0, 0])
    y = sqrt_fq2(x**3 + b2)
    if y.coeffs[0] % 2 != y1_mod_2:
        y = FQ2((y * -1).coeffs)
    assert is_on_curve((x, y, FQ2([1, 0])), b2)
    return x, y, FQ2([1, 0])


def sign(m: bytes, k: int) -> Tuple[int, int]:
    return compress_G2(multiply(hash_to_G2(m), k))


def privtopub(k: int) -> int:
    return compress_G1(multiply(G1, k))


def verify(m: bytes, pub: int, sig: bytes) -> bool:
    final_exponentiation = final_exponentiate(
        pairing(FQP_point_to_FQ2_point(decompress_G2(sig)), G1, False) *
        pairing(FQP_point_to_FQ2_point(hash_to_G2(m)), neg(decompress_G1(pub)), False)
    )
    return final_exponentiation == FQ12.one()


def aggregate_sigs(sigs: Iterable[bytes]) -> Tuple[int, int]:
    o = Z2
    for s in sigs:
        o = FQP_point_to_FQ2_point(add(o, decompress_G2(s)))
    return compress_G2(o)


def aggregate_pubs(pubs: Iterable[int]) -> int:
    o = Z1
    for p in pubs:
        o = add(o, decompress_G1(p))
    return compress_G1(o)
