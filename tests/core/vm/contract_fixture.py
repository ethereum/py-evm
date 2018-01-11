# contract code to be deployed
contract_lll_code = ['seq',
                        ['return',  # noqa: E127
                            0,
                            ['lll',
                                ['seq',
                                    ['mstore', 32, 1461501637330902918203684832716283019655932542976],  # noqa: E501
                                    ['uclamplt', ['calldataload', 0], ['mload', 32]],
                                    ['assert', ['call', 0, ['calldataload', 0], ['calldataload', 32], 0, 0, 0, 0]],  # noqa: E501
                                    'stop'],
                            0]]]  # noqa: E128


# compiled byte code
contract_bytecode = b'0x61003e567401000000000000000000000000000000000000000060205260003560205181101558575060006000600060006020356000356000f1155857005b61000461003e0361000460003961000461003e036000f3'  # noqa: E501

# address where this contract will be deployed
contract_address = b'\xdb\xcd\xfc\xf2\xea!\xcd\x0c\xa5d\xaay\x8b;\xf0\xe4\xe2\x98S\xca'
