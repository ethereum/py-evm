# Forwarder Contract
simple_forwarder_contract_lll_code = ['seq',
                                        ['return',  # noqa: E127
                                            0,
                                            ['lll',
                                                ['seq',
                                                    ['mstore', 32, 1461501637330902918203684832716283019655932542976],  # noqa: E501
                                                    ['uclamplt', ['calldataload', 0], ['mload', 32]],  # noqa: E501
                                                    ['calldatacopy', 64, 64, 32],
                                                    ['calldatacopy', 96, 32, ['calldatasize']],
                                                    ['assert', ['call', ['sub', ['gas'], 100000], ['calldataload', 0], ['calldataload', 32], 64, ['calldatasize'], 0, 0]],  # noqa: E501
                                                    'stop'],
                                            0]]]  # noqa: E128


# Normal PAYGAS Contract
PAYGAS_contract_normal_lll_code = ['seq',
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
                                        0]]]  # noqa: E128


# PAYGAS Contract that trigger PAYGAS opcode twice
PAYGAS_contract_triggered_twice_lll_code = ['seq',
                                            ['return',  # noqa: E127
                                                0,
                                                ['lll',
                                                    ['seq',
                                                        ['paygas', ['calldataload', 64]],
                                                        # Transfer value
                                                        ['mstore', 128, 1461501637330902918203684832716283019655932542976],  # noqa: E501
                                                        ['uclamplt', ['calldataload', 0], ['mload', 128]],  # noqa: E501
                                                        ['assert', ['call', ['sub', ['gas'], 100000], ['calldataload', 0], ['calldataload', 32], 0, 0, 0, 0]],  # noqa: E501
                                                        ['paygas', ['mul', ['calldataload', 64], 10]],  # noqa: E501
                                                        'stop'],
                                                0]]]  # noqa: E128
