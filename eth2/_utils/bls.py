from typing import (  # noqa: F401
    Dict,
    Sequence,
    Tuple,
    Union,
)

from eth_utils import (
    big_endian_to_int,
    ValidationError,
)

from py_ecc.optimized_bls12_381 import (  # NOQA
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
    field_modulus as q,
    b,
    b2,
    is_on_curve,
    curve_order,
    final_exponentiate
)
from eth.beacon._utils.hash import hash_eth2

from eth.beacon.typing import (
    BLSPubkey,
    BLSSignature,
)

G2_cofactor = 305502333931268344200999753193121504214466019254188142667664032982267604182971884026507427359259977847832272839041616661285803823378372096355777062779109  # noqa: E501
FQ2_order = q ** 2 - 1
eighth_roots_of_unity = [
    FQ2([1, 1]) ** ((FQ2_order * k) // 8)
    for k in range(8)
]


#
# Helpers
#
def FQP_point_to_FQ2_point(pt: Tuple[FQP, FQP, FQP]) -> Tuple[FQ2, FQ2, FQ2]:
    """
    Transform FQP to FQ2 for type hinting.
    """
    return (
        FQ2(pt[0].coeffs),
        FQ2(pt[1].coeffs),
        FQ2(pt[2].coeffs),
    )


def modular_squareroot(value: int) -> FQP:
    """
    ``modular_squareroot(x)`` returns the value ``y`` such that ``y**2 % q == x``,
    and None if this is not possible. In cases where there are two solutions,
    the value with higher imaginary component is favored;
    if both solutions have equal imaginary component the value with higher real
    component is favored.
    """
    candidate_squareroot = value ** ((FQ2_order + 8) // 16)
    check = candidate_squareroot ** 2 / value
    if check in eighth_roots_of_unity[::2]:
        x1 = candidate_squareroot / eighth_roots_of_unity[eighth_roots_of_unity.index(check) // 2]
        x2 = FQ2([-x1.coeffs[0], -x1.coeffs[1]])  # x2 = -x1
        return x1 if (x1.coeffs[1], x1.coeffs[0]) > (x2.coeffs[1], x2.coeffs[0]) else x2
    return None


def hash_to_G2(message: bytes, domain: int) -> Tuple[FQ2, FQ2, FQ2]:
    domain_in_bytes = domain.to_bytes(8, 'big')

    # Initial candidate x coordinate
    x_re = big_endian_to_int(hash_eth2(domain_in_bytes + b'\x01' + message))
    x_im = big_endian_to_int(hash_eth2(domain_in_bytes + b'\x02' + message))
    x_coordinate = FQ2([x_re, x_im])  # x_re + x_im * i

    # Test candidate y coordinates until a one is found
    while 1:
        y_coordinate_squared = x_coordinate ** 3 + FQ2([4, 4])  # The curve is y^2 = x^3 + 4(i + 1)
        y_coordinate = modular_squareroot(y_coordinate_squared)
        if y_coordinate is not None:  # Check if quadratic residue found
            break
        x_coordinate += FQ2([1, 0])  # Add 1 and try again

    return multiply(
        (x_coordinate, y_coordinate, FQ2([1, 0])),
        G2_cofactor
    )


#
# G1
#
def compress_G1(pt: Tuple[FQ, FQ, FQ]) -> int:
    x, y = normalize(pt)
    return x.n + 2**383 * (y.n % 2)


def decompress_G1(pt: int) -> Tuple[FQ, FQ, FQ]:
    if pt == 0:
        return (FQ(1), FQ(1), FQ(0))
    x = pt % 2**383
    y_mod_2 = pt // 2**383
    y = pow((x**3 + b.n) % q, (q + 1) // 4, q)

    if pow(y, 2, q) != (x**3 + b.n) % q:
        raise ValueError(
            "he given point is not on G1: y**2 = x**3 + b"
        )
    if y % 2 != y_mod_2:
        y = q - y
    return (FQ(x), FQ(y), FQ(1))


#
# G2
#
def compress_G2(pt: Tuple[FQP, FQP, FQP]) -> Tuple[int, int]:
    if not is_on_curve(pt, b2):
        raise ValueError(
            "The given point is not on the twisted curve over FQ**2"
        )
    x, y = normalize(pt)
    return (
        int(x.coeffs[0] + 2**383 * (y.coeffs[0] % 2)),
        int(x.coeffs[1])
    )


def decompress_G2(p: Tuple[int, int]) -> Tuple[FQP, FQP, FQP]:
    x1 = p[0] % 2**383
    y1_mod_2 = p[0] // 2**383
    x2 = p[1]
    x = FQ2([x1, x2])
    if x == FQ2([0, 0]):
        return FQ2([1, 0]), FQ2([1, 0]), FQ2([0, 0])
    y = modular_squareroot(x**3 + b2)
    if y.coeffs[0] % 2 != y1_mod_2:
        y = FQ2((y * -1).coeffs)
    if not is_on_curve((x, y, FQ2([1, 0])), b2):
        raise ValueError(
            "The given point is not on the twisted curve over FQ**2"
        )
    return x, y, FQ2([1, 0])


#
# APIs
#
def sign(message: bytes,
         privkey: int,
         domain: int) -> BLSSignature:
    return BLSSignature(
        compress_G2(
            multiply(
                hash_to_G2(message, domain),
                privkey
            )
        ))


def privtopub(k: int) -> BLSPubkey:
    return BLSPubkey(compress_G1(multiply(G1, k)))


def verify(message: bytes, pubkey: BLSPubkey, signature: BLSSignature, domain: int) -> bool:
    try:
        final_exponentiation = final_exponentiate(
            pairing(
                FQP_point_to_FQ2_point(decompress_G2(signature)),
                G1,
                final_exponentiate=False,
            ) *
            pairing(
                FQP_point_to_FQ2_point(hash_to_G2(message, domain)),
                neg(decompress_G1(pubkey)),
                final_exponentiate=False,
            )
        )
        return final_exponentiation == FQ12.one()
    except (ValidationError, ValueError, AssertionError):
        return False


def aggregate_signatures(signatures: Sequence[BLSSignature]) -> BLSSignature:
    o = Z2
    for s in signatures:
        o = FQP_point_to_FQ2_point(add(o, decompress_G2(s)))
    return BLSSignature(compress_G2(o))


def aggregate_pubkeys(pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
    o = Z1
    for p in pubkeys:
        o = add(o, decompress_G1(p))
    return BLSPubkey(compress_G1(o))


def verify_multiple(pubkeys: Sequence[BLSPubkey],
                    messages: Sequence[bytes],
                    signature: BLSSignature,
                    domain: int) -> bool:
    len_msgs = len(messages)

    if len(pubkeys) != len_msgs:
        raise ValidationError(
            "len(pubkeys) (%s) should be equal to len(messages) (%s)" % (
                len(pubkeys), len_msgs
            )
        )

    try:
        o = FQ12([1] + [0] * 11)
        for m_pubs in set(messages):
            # aggregate the pubs
            group_pub = Z1
            for i in range(len_msgs):
                if messages[i] == m_pubs:
                    group_pub = add(group_pub, decompress_G1(pubkeys[i]))

            o *= pairing(hash_to_G2(m_pubs, domain), group_pub, final_exponentiate=False)
        o *= pairing(decompress_G2(signature), neg(G1), final_exponentiate=False)

        final_exponentiation = final_exponentiate(o)
        return final_exponentiation == FQ12.one()
    except (ValidationError, ValueError, AssertionError):
        return False
