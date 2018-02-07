# Simple Transfer Contract
# contract code to be deployed
simple_transfer_contract_lll_code = ['seq',
                                        ['return',  # noqa: E127
                                            0,
                                            ['lll',
                                                ['seq',
                                                    ['mstore', 32, 1461501637330902918203684832716283019655932542976],  # noqa: E501
                                                    ['uclamplt', ['calldataload', 0], ['mload', 32]],  # noqa: E501
                                                    ['assert', ['call', 0, ['calldataload', 0], ['calldataload', 32], 0, 0, 0, 0]],  # noqa: E501
                                                    'stop'],
                                            0]]]  # noqa: E128


simple_factory_contract_bytecode = b'\x61\xbe\xef\x60\x20\x52\x60\x02\x60\x3e\xf3'


# CREATE2 Contract
# This contract will deploy a new contract and increment it's only storage variable 'nonce'
# every time it's invoked.
# Contract address: generate_CREATE2_contract_address(nonce, simple_factory_contract_bytecode)
# The bytecode of every new contract deployed is b'\xbe\xef'
CREATE2_contract_lll_code = ['seq',
                                ['return',  # noqa: E127
                                    0,
                                    ['lll',
                                        ['seq',
                                            ['mstore', 32, ['sload', 0]],
                                            ['mstore', 64, 118167469832824678325960435],
                                            ['clamp_nonzero', ['create2', ['mload', 32], ['mload', 32], 85, 11]],  # noqa: E501
                                            ['sstore', 0, ['add', ['mload', 32], 1]],
                                            'stop'],
                                    0]]]  # noqa: E128
