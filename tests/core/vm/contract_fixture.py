from eth_utils import decode_hex

from evm.utils.address import generate_CREATE2_contract_address

# Simple Transfer Contract
# contract code to be deployed
simple_transfer_contract = {
    'lll_code': ['seq',
                    ['return',  # noqa: E127
                        0,
                        ['lll',
                            ['seq',
                                ['mstore', 32, 1461501637330902918203684832716283019655932542976],  # noqa: E501
                                ['uclamplt', ['calldataload', 0], ['mload', 32]],  # noqa: E501
                                ['assert', ['call', 0, ['calldataload', 0], ['calldataload', 32], 0, 0, 0, 0]],  # noqa: E501
                                'stop'],
                        0]]],  # noqa: E128
    # compiled byte code
    'bytecode': b'0x61003e567401000000000000000000000000000000000000000060205260003560205181101558575060006000600060006020356000356000f1155857005b61000461003e0361000460003961000461003e036000f3',  # noqa: E501
    # address where this contract will be deployed
    'address': generate_CREATE2_contract_address(
        b'',
        decode_hex(b'0x61003e567401000000000000000000000000000000000000000060205260003560205181101558575060006000600060006020356000356000f1155857005b61000461003e0361000460003961000461003e036000f3')  # noqa: E501
    )
}


simple_contract_factory_bytecode = b'\x61\xbe\xef\x60\x20\x52\x60\x02\x60\x3e\xf3'


# CREATE2 Contract
# This contract will deploy a new contract and increment it's only storage variable 'nonce'
# every time it's invoked.
# Contract address: generate_CREATE2_contract_address(nonce, simple_contract_factory_bytecode)
# The bytecode of every new contract deployed is b'\xbe\xef'
CREATE2_contract = {
    'lll_code': ['seq',
                    ['return',  # noqa: E127
                        0,
                        ['lll',
                            ['seq',
                                ['mstore', 32, ['sload', 0]],
                                ['mstore', 64, 118167469832824678325960435],
                                ['clamp_nonzero', ['create2', ['mload', 32], ['mload', 32], 85, 11]],  # noqa: E501
                                ['sstore', 0, ['add', ['mload', 32], 1]],
                                'stop'],
                        0]]],  # noqa: E128
    # compiled byte code
    'bytecode': b'0x610039566000546020526a61beef6020526002603ef3604052600b6055602051602051fe8061002957600080fd5b50600160205101600055005b61000461003903610004600039610004610039036000f3',  # noqa: E501
    # address where this contract will be deployed
    'address': generate_CREATE2_contract_address(
        b'',
        decode_hex(b'0x610039566000546020526a61beef6020526002603ef3604052600b6055602051602051fe8061002957600080fd5b50600160205101600055005b61000461003903610004600039610004610039036000f3')  # noqa: E501
    )
}


# Normal PAYGAS Contract
PAYGAS_contract_normal = {
    'lll_code': ['seq',
                    ['return',  # noqa: E127
                        0,
                        ['lll',
                            ['seq',
                                ['paygas', ['calldataload', 64]],
                                # Transfer value
                                ['mstore', 128, 1461501637330902918203684832716283019655932542976],  # noqa: E501
                                ['uclamplt', ['calldataload', 0], ['mload', 128]],  # noqa: E501
                                ['assert', ['call', ['sub', ['gas'], 100000], ['calldataload', 0], ['calldataload', 32], 0, 0, 0, 0]],  # noqa: E501
                                'stop'],
                        0]]],  # noqa: E128
    # compiled byte code
    'bytecode': b'0x61005356604035f55074010000000000000000000000000000000000000000608052600035608051811061002e57600080fd5b506000600060006000602035600035620186a05a03f161004d57600080fd5b005b61000461005303610004600039610004610053036000f3',  # noqa: E501
    # address where this contract will be deployed
    'address': generate_CREATE2_contract_address(
        b'',
        decode_hex(b'0x61005356604035f55074010000000000000000000000000000000000000000608052600035608051811061002e57600080fd5b506000600060006000602035600035620186a05a03f161004d57600080fd5b005b61000461005303610004600039610004610053036000f3')  # noqa: E501
    )
}
