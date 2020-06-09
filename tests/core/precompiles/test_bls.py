from py_ecc.optimized_bls12_381.optimized_curve import G1, G2, neg, FQ12
from eth.precompiles.bls import _pairing, _serialize_g2, _serialize_g1

def test_pairing_precompile():
    # assert pairing(G1, G2) * pairing(neg(G1), G2) == FQ12.one()
    serialized_G1 = _serialize_g1(G1)
    serialized_G2 = _serialize_g2(G2)
    serialized_neg_G1 = _serialize_g1(neg(G1))
    input_data = serialized_G1 + serialized_G2 + serialized_neg_G1 + serialized_G2
    assert _pairing(input_data)
