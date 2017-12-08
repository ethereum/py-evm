import os

import rlp

from viper import compiler

from eth_abi import (
    decode_abi,
    encode_abi,
)

from eth_keys import KeyAPI

import eth_utils

from evm.utils.address import generate_contract_address

from evm.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction,
    SpuriousDragonUnsignedTransaction,
)

from config import GASPRICE

sha3 = eth_utils.crypto.keccak

WITHDRAW_HASH = sha3("withdraw")

_valmgr_abi = None
_valmgr_ct = None
_valmgr_code = None
_valmgr_bytecode = None
_valmgr_addr = None
_valmgr_sender_addr = None
_valmgr_tx = None

# old one, address=0xCb969cAAad21A78a24083164ffa81604317Ab603
viper_rlp_decoder_tx = rlp.decode(eth_utils.decode_hex("0xf90237808506fc23ac00830330888080b902246102128061000e60003961022056600060007f010000000000000000000000000000000000000000000000000000000000000060003504600060c082121515585760f882121561004d5760bf820336141558576001905061006e565b600181013560f783036020035260005160f6830301361415585760f6820390505b5b368112156101c2577f010000000000000000000000000000000000000000000000000000000000000081350483602086026040015260018501945060808112156100d55760018461044001526001828561046001376001820191506021840193506101bc565b60b881121561014357608081038461044001526080810360018301856104600137608181141561012e5760807f010000000000000000000000000000000000000000000000000000000000000060018401350412151558575b607f81038201915060608103840193506101bb565b60c08112156101b857600182013560b782036020035260005160388112157f010000000000000000000000000000000000000000000000000000000000000060018501350402155857808561044001528060b6838501038661046001378060b6830301830192506020810185019450506101ba565bfe5b5b5b5061006f565b601f841315155857602060208502016020810391505b6000821215156101fc578082604001510182826104400301526020820391506101d8565b808401610420528381018161044003f350505050505b6000f31b2d4f"), SpuriousDragonTransaction)
# TODO: new one but for now not working fine. address=0x6b2A423C7915e984ebCD3aD2B86ba815A7D4ae6d
# viper_rlp_decoder_tx = rlp.decode(utils.parse_as_bin("0xf9035b808506fc23ac0083045ef88080b903486103305660006109ac5260006109cc527f0100000000000000000000000000000000000000000000000000000000000000600035046109ec526000610a0c5260006109005260c06109ec51101515585760f86109ec51101561006e5760bf6109ec510336141558576001610a0c52610098565b60013560f76109ec51036020035260005160f66109ec510301361415585760f66109ec5103610a0c525b61010060016064818352015b36610a0c511015156100b557610291565b7f0100000000000000000000000000000000000000000000000000000000000000610a0c5135046109ec526109cc5160206109ac51026040015260016109ac51016109ac5260806109ec51101561013b5760016109cc5161044001526001610a0c516109cc5161046001376001610a0c5101610a0c5260216109cc51016109cc52610281565b60b86109ec5110156101d15760806109ec51036109cc51610440015260806109ec51036001610a0c51016109cc51610460013760816109ec5114156101ac5760807f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350410151558575b607f6109ec5103610a0c5101610a0c5260606109ec51036109cc51016109cc52610280565b60c06109ec51101561027d576001610a0c51013560b76109ec510360200352600051610a2c526038610a2c5110157f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350402155857610a2c516109cc516104400152610a2c5160b66109ec5103610a0c51016109cc516104600137610a2c5160b66109ec5103610a0c510101610a0c526020610a2c51016109cc51016109cc5261027f565bfe5b5b5b81516001018083528114156100a4575b5050601f6109ac511115155857602060206109ac5102016109005260206109005103610a0c5261010060016064818352015b6000610a0c5112156102d45761030a565b61090051610a0c516040015101610a0c51610900516104400301526020610a0c5103610a0c5281516001018083528114156102c3575b50506109cc516109005101610420526109cc5161090051016109005161044003f35b61000461033003610004600039610004610330036000f31b2d4f"), Transaction)

viper_rlp_decoder_addr = eth_utils.to_checksum_address(
    generate_contract_address(eth_utils.to_canonical_address(viper_rlp_decoder_tx.sender), 0)
)

sighasher_tx = rlp.decode(eth_utils.decode_hex("0xf9016d808506fc23ac0083026a508080b9015a6101488061000e6000396101565660007f01000000000000000000000000000000000000000000000000000000000000006000350460f8811215610038576001915061003f565b60f6810391505b508060005b368312156100c8577f01000000000000000000000000000000000000000000000000000000000000008335048391506080811215610087576001840193506100c2565b60b881121561009d57607f8103840193506100c1565b60c08112156100c05760b68103600185013560b783036020035260005101840193505b5b5b50610044565b81810360388112156100f4578060c00160005380836001378060010160002060e052602060e0f3610143565b61010081121561010557600161011b565b6201000081121561011757600261011a565b60035b5b8160005280601f038160f701815382856020378282600101018120610140526020610140f350505b505050505b6000f31b2d4f"), SpuriousDragonTransaction)
sighasher_addr = eth_utils.to_checksum_address(
    generate_contract_address(eth_utils.to_canonical_address(sighasher_tx.sender), 0)
)

def mk_validation_code(address):
    '''
    validation_code = """
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
    """.format(utils.checksum_encode(address))
    return serpent.compile(validation_code)
    '''
    # The precompiled bytecode of the validation code which
    # verifies EC signatures
    validation_code_bytecode = b"a\x009\x80a\x00\x0e`\x009a\x00GV`\x80`\x00`\x007` "
    validation_code_bytecode += b"`\x00`\x80`\x00`\x00`\x01a\x0b\xb8\xf1Ps"
    validation_code_bytecode += address
    validation_code_bytecode += b"`\x00Q\x14` R` ` \xf3[`\x00\xf3"
    return validation_code_bytecode

def sign(message, privkey):
    '''@privkey: Key type
    '''
    keys = KeyAPI()
    signature = keys.ecdsa_sign(message, privkey)
    v, r, s = signature.vrs
    v += 27
    signature_bytes = b''.join([item.to_bytes(32, 'big') for item in (v, r, s)])
    return signature_bytes

def get_valmgr_abi():
    global _valmgr_abi, _valmgr_code
    if not _valmgr_abi:
        _valmgr_abi = compiler.mk_full_signature(get_valmgr_code())
    return _valmgr_abi

def get_valmgr_code():
    global _valmgr_code
    if not _valmgr_code:
        mydir = os.path.dirname(__file__)
        valmgr_path = os.path.join(mydir, '../contracts/validator_manager.v.py')
        _valmgr_code = open(valmgr_path).read()
    return _valmgr_code

def get_valmgr_bytecode():
    global _valmgr_bytecode
    if not _valmgr_bytecode:
        _valmgr_bytecode = compiler.compile(get_valmgr_code())
    return _valmgr_bytecode

def get_valmgr_addr():
    global _valmgr_addr
    if not _valmgr_addr:
        create_valmgr_tx()
    return _valmgr_addr

def get_valmgr_sender_addr():
    global _valmgr_sender_addr
    if not _valmgr_sender_addr:
        create_valmgr_tx()
    return _valmgr_sender_addr

def get_valmgr_tx():
    global _valmgr_tx
    if not _valmgr_tx:
        create_valmgr_tx()
    return _valmgr_tx

def create_valmgr_tx(gasprice=GASPRICE):
    global _valmgr_sender_addr, _valmgr_addr, _valmgr_tx
    bytecode = get_valmgr_bytecode()
    v = 27
    r = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    s = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    tx = SpuriousDragonTransaction(0, gasprice, 3000000, b'', 0, bytecode, v, r, s)
    valmgr_sender_addr = tx.sender
    valmgr_addr = eth_utils.to_checksum_address(
        generate_contract_address(eth_utils.to_canonical_address(valmgr_sender_addr), 0)
    )
    _valmgr_sender_addr = eth_utils.to_checksum_address(valmgr_sender_addr)
    _valmgr_addr = valmgr_addr
    _valmgr_tx = tx

def mk_initiating_contracts(sender_privkey, sender_starting_nonce, gasprice=GASPRICE):
    """Make transactions of createing initial contracts
    Including rlp_decoder, sighasher and validator_manager
    """
    o = []
    nonce = sender_starting_nonce
    global viper_rlp_decoder_tx, sighasher_tx
    # the sender gives all senders of the txs money, and append the
    # money-giving tx with the original tx to the return list
    for tx in (viper_rlp_decoder_tx, sighasher_tx, get_valmgr_tx()):
        o.append(
            SpuriousDragonUnsignedTransaction(
                nonce,
                gasprice,
                500000,
                tx.sender,
                tx.gas * tx.gas_price + tx.value,
                b'',
            ).as_signed_transaction(sender_privkey)
        )
        nonce += 1
    o += [viper_rlp_decoder_tx, sighasher_tx, get_valmgr_tx()]
    return o

def get_func_abi(func_name, contract_abi):
    for func_abi in contract_abi:
        if func_abi['name'] == func_name:
            return func_abi
    raise ValueError('ABI of function {} is not found in vmc'.format(func_name))

def mk_contract_tx_obj(
        func_name,
        args,
        contract_addr,
        contract_abi,
        sender_addr,
        value,
        gas,
        gas_price):
    func_abi = get_func_abi(func_name, contract_abi)
    arg_types = [arg_abi['type'] for arg_abi in func_abi['inputs']]
    func_selector = eth_utils.function_abi_to_4byte_selector(func_abi)
    data = func_selector + encode_abi(arg_types, args)
    data = eth_utils.encode_hex(data)
    obj = {
        'from': eth_utils.address.to_checksum_address(sender_addr),
        'to': eth_utils.address.to_checksum_address(contract_addr),
        'value': value,
        'gas': gas,
        'gas_price': gas_price,
        'data': data,
    }
    return obj

def mk_vmc_tx_obj(
        func,
        args,
        sender_addr,
        value,
        gas,
        gas_price):
    vmc_abi = get_valmgr_abi()
    vmc_addr = get_valmgr_addr()
    return mk_contract_tx_obj(
        func,
        args,
        vmc_addr,
        vmc_abi,
        sender_addr,
        value,
        gas,
        gas_price,
    )

def decode_contract_call_result(func_name, contract_abi, result):
    func_abi = get_func_abi(func_name, contract_abi)
    output_types = [output_abi['type'] for output_abi in func_abi['outputs']]
    return decode_abi(output_types, result)[0]  # not sure why it's a tuple

def decode_vmc_call_result(func_name, result):
    vmc_abi = get_valmgr_abi()
    return decode_contract_call_result(func_name, vmc_abi, result)
