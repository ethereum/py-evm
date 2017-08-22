from rlp.utils import decode_hex

from evm.utils.keccak import keccak


MSG = b'message'
MSGHASH = keccak(MSG)

# This is a sample of signatures generated with a known-good implementation of the ECDSA
# algorithm, which we use to test our ECC backends. If necessary, it can be generated from scratch
# with the following code:
"""
from devp2p import crypto
from rlp.utils import encode_hex
msg = b'message'
msghash = crypto.sha3(b'message')
for secret in ['alice', 'bob', 'eve']:
    print("'{}': dict(".format(secret))
    privkey = crypto.mk_privkey(secret)
    pubkey = crypto.privtopub(privkey)
    print("    privkey='{}',".format(encode_hex(privkey)))
    print("    pubkey='{}',".format(encode_hex(crypto.privtopub(privkey))))
    ecc = crypto.ECCx(raw_privkey=privkey)
    sig = ecc.sign(msghash)
    print("    sig='{}',".format(encode_hex(sig)))
    print("    raw_sig='{}')".format(crypto._decode_sig(sig)))
    assert crypto.ecdsa_recover(msghash, sig) == pubkey
"""
SECRETS = {
    "alice": dict(
        privkey=decode_hex(b'9c0257114eb9399a2985f8e75dad7600c5d89fe3824ffa99ec1c3eb8bf3b0501'),
        pubkey=decode_hex(b'5eed5fa3a67696c334762bb4823e585e2ee579aba3558d9955296d6c04541b426078dbd48d74af1fd0c72aa1a05147cf17be6b60bdbed6ba19b08ec28445b0ca'),  # noqa: E501
        sig=decode_hex(b'b20e2ea5d3cbaa83c1e0372f110cf12535648613b479b64c1a8c1a20c5021f380434d07ec5795e3f789794351658e80b7faf47a46328f41e019d7b853745cdfd01'),  # noqa: E501
        raw_sig=(28,
                 80536744857756143861726945576089915884233437828013729338039544043241440681784,
                 1902566422691403459035240420865094128779958320521066670269403689808757640701)),
    "bob": dict(
        privkey=decode_hex(b'38e47a7b719dce63662aeaf43440326f551b8a7ee198cee35cb5d517f2d296a2'),
        pubkey=decode_hex(b'347746ccb908e583927285fa4bd202f08e2f82f09c920233d89c47c79e48f937d049130e3d1c14cf7b21afefc057f71da73dec8e8ff74ff47dc6a574ccd5d570'),  # noqa: E501
        sig=decode_hex(b'5c48ea4f0f2257fa23bd25e6fcb0b75bbe2ff9bbda0167118dab2bb6e31ba76e691dbdaf2a231fc9958cd8edd99507121f8184042e075cf10f98ba88abff1f3601'),  # noqa: E501
        raw_sig=(28,
                 41741612198399299636429810387160790514780876799439767175315078161978521003886,
                 47545396818609319588074484786899049290652725314938191835667190243225814114102)),
    "eve": dict(
        privkey=decode_hex(b'876be0999ed9b7fc26f1b270903ef7b0c35291f89407903270fea611c85f515c'),
        pubkey=decode_hex(b'c06641f0d04f64dba13eac9e52999f2d10a1ff0ca68975716b6583dee0318d91e7c2aed363ed22edeba2215b03f6237184833fd7d4ad65f75c2c1d5ea0abecc0'),  # noqa: E501
        sig=decode_hex(b'babeefc5082d3ca2e0bc80532ab38f9cfb196fb9977401b2f6a98061f15ed603603d0af084bf906b2cdf6cdde8b2e1c3e51a41af5e9adec7f3643b3f1aa2aadf00'),  # noqa: E501
        raw_sig=(27,
                 84467545608142925331782333363288012579669270632210954476013542647119929595395,
                 43529886636775750164425297556346136250671451061152161143648812009114516499167))
    }
